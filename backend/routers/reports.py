"""Report generation endpoints"""
import io
from typing import List
import pandas as pd
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse

router = APIRouter(tags=["Reports"])


async def extract_and_merge_data(files: List[UploadFile]):
    if not files:
        raise HTTPException(status_code=400, detail="Dosya yüklenmedi")

    all_dfs = []
    for file in files:
        content = await file.read()
        try:
            df = pd.read_excel(io.BytesIO(content))
            all_dfs.append(df)
            await file.seek(0)
        except Exception as e:
            print(f"Error reading {file.filename}: {e}")
            continue

    if not all_dfs:
        raise HTTPException(status_code=400, detail="Geçerli bir Excel dosyası okunamadı")

    merged_df = pd.concat(all_dfs, ignore_index=True)

    if 'Mecra' in merged_df.columns:
        merged_df = merged_df.dropna(subset=['Mecra'])

    def map_mecra(val):
        if pd.isna(val):
            return "Diğer"
        val_str = str(val).strip()
        if "Elektronik Basın" in val_str:
            return "İnternet"
        if "Görsel Basın" in val_str:
            return "TV"
        if "Yazılı Basın" in val_str:
            return "Yazılı Basın"
        return val_str

    if 'Mecra' in merged_df.columns:
        merged_df['Mecra_Grup'] = merged_df['Mecra'].apply(map_mecra)
    else:
        merged_df['Mecra_Grup'] = "Diğer"

    if 'Erişim' in merged_df.columns:
        merged_df['Erişim'] = pd.to_numeric(merged_df['Erişim'], errors='coerce').fillna(0)
    if 'Re.Eş. (TRY)' in merged_df.columns:
        merged_df['Re.Eş. (TRY)'] = pd.to_numeric(merged_df['Re.Eş. (TRY)'], errors='coerce').fillna(0)

    summary = merged_df.groupby('Mecra_Grup').size().reset_index(name='Haber Adedi')
    summary.rename(columns={'Mecra_Grup': 'Mecra'}, inplace=True)

    if 'Erişim' in merged_df.columns:
        erisim_sum = merged_df.groupby('Mecra_Grup')['Erişim'].sum().reset_index(name='Erişim')
        summary = summary.merge(erisim_sum.rename(columns={'Mecra_Grup': 'Mecra'}), on='Mecra')

    if 'Re.Eş. (TRY)' in merged_df.columns:
        re_sum = merged_df.groupby('Mecra_Grup')['Re.Eş. (TRY)'].sum().reset_index(name='Reklam Eşdeğeri(TL)')
        summary = summary.merge(re_sum.rename(columns={'Mecra_Grup': 'Mecra'}), on='Mecra')

    order = {'Yazılı Basın': 0, 'İnternet': 1, 'TV': 2}
    summary['sort_order'] = summary['Mecra'].map(order).fillna(99)
    summary = summary.sort_values('sort_order').drop(columns=['sort_order']).reset_index(drop=True)

    return merged_df, summary


@router.post("/preview-report")
async def preview_report(files: List[UploadFile] = File(...)):
    try:
        _, summary = await extract_and_merge_data(files)

        numeric_cols = summary.select_dtypes(include=['number']).columns.tolist()
        totals = summary[numeric_cols].sum()
        totals_dict = {'Mecra': 'Toplam'}
        for col in numeric_cols:
            totals_dict[col] = float(totals[col])

        summary_records = summary.to_dict(orient='records')
        labels = summary['Mecra'].tolist()

        chart_data = {
            'labels': labels,
            'haber_adedi': summary['Haber Adedi'].tolist(),
            'erisim': summary['Erişim'].tolist() if 'Erişim' in summary.columns else [],
            'reklam': summary['Reklam Eşdeğeri(TL)'].tolist() if 'Reklam Eşdeğeri(TL)' in summary.columns else []
        }

        return {
            "success": True,
            "data": {
                "summary_table": summary_records,
                "totals": totals_dict,
                "chart_data": chart_data
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/generate-report")
async def generate_report(files: List[UploadFile] = File(...), layout_type: str = Form("standard")):
    """Merge multiple Excel files and generate a summary report with charts."""
    try:
        merged_df, summary = await extract_and_merge_data(files)

        numeric_cols = summary.select_dtypes(include=['number']).columns.tolist()
        totals = {col: summary[col].sum() for col in numeric_cols}
        data_row_count = len(summary)

        tum_veriler_df = merged_df.drop(columns=['Mecra_Grup'], errors='ignore')

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            tum_veriler_df.to_excel(writer, sheet_name='Tüm Veriler', index=False)
            summary.to_excel(writer, sheet_name='Yönetici Özeti', index=False, startrow=0, startcol=0)

            workbook = writer.book
            summary_sheet = writer.sheets['Yönetici Özeti']

            summary_sheet.set_column('A:A', 15)
            summary_sheet.set_column('B:B', 12)
            summary_sheet.set_column('C:C', 15)
            summary_sheet.set_column('D:D', 20)

            if layout_type == "modern":
                header_bg = '#4A90E2'
                header_font = 'white'
                chart_style = 2
            else:
                header_bg = '#D7E4BC'
                header_font = 'black'
                chart_style = 10

            header_format = workbook.add_format({
                'bold': True,
                'bg_color': header_bg,
                'font_color': header_font,
                'border': 1
            })

            totals_format = workbook.add_format({
                'bold': True,
                'bg_color': '#FFF2CC',
                'border': 1,
                'num_format': '#,##0'
            })

            totals_text_format = workbook.add_format({
                'bold': True,
                'bg_color': '#FFF2CC',
                'border': 1
            })

            for col_num, value in enumerate(summary.columns.values):
                summary_sheet.write(0, col_num, value, header_format)

            totals_row_idx = data_row_count + 1
            last_data_row = data_row_count + 1

            summary_sheet.write(totals_row_idx, 0, 'Toplam', totals_text_format)
            summary_sheet.write_formula(totals_row_idx, 1, f'=SUM(B2:B{last_data_row})', totals_format, totals.get('Haber Adedi', 0))
            summary_sheet.write_formula(totals_row_idx, 2, f'=SUM(C2:C{last_data_row})', totals_format, totals.get('Erişim', 0))
            summary_sheet.write_formula(totals_row_idx, 3, f'=SUM(D2:D{last_data_row})', totals_format, totals.get('Reklam Eşdeğeri(TL)', 0))

            def add_pie_chart(col_idx, title, pos_cell, scale=0.75):
                chart = workbook.add_chart({'type': 'pie'})
                chart.add_series({
                    'name': title,
                    'categories': ['Yönetici Özeti', 1, 0, data_row_count, 0],
                    'values': ['Yönetici Özeti', 1, col_idx, data_row_count, col_idx],
                    'data_labels': {'percentage': True, 'category': False},
                })
                chart.set_title({'name': title})
                chart.set_style(chart_style)
                summary_sheet.insert_chart(pos_cell, chart, {'x_scale': scale, 'y_scale': scale})

            add_pie_chart(1, 'HABER ADEDİ DAĞILIM YÜZDESİ', 'A10')

            col_map = {col: i for i, col in enumerate(summary.columns)}
            if 'Erişim' in col_map:
                add_pie_chart(col_map['Erişim'], 'ERİŞİM DAĞILIM YÜZDESİ', 'E10')

            if 'Reklam Eşdeğeri(TL)' in col_map:
                add_pie_chart(col_map['Reklam Eşdeğeri(TL)'], 'REKLAM EŞDEĞERİ (TL) DAĞILIM YÜZDESİ', 'L10')

        output.seek(0)
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=MTM_Yonetici_Ozeti.xlsx"}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rapor oluşturulurken hata: {str(e)}")
