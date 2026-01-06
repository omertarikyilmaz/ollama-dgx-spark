Amacimiz ollamanin en ideal modellerinden birini kullanarak hizli bir sekilde pre cache yani kv cache arayuz uzerinden verilicek olan gazete haberlerini her alan icin ozel olarak json formatinda dondurmelelrini saglamak. ama kullanici kv cache ile modeli hizlandirmayi yonelik adimi kendisi arayuz uzerinden ozel bir sekilde ayarlayip degistirebilmeli her islem icin farkli kv cache edilmis sey kullanabilmeli model her zaman json olarak cevap vermeli kullanici sadece haberi vericek ve onrke sekilde cevap aalbilmeli 

{
 "model": "gpt-4o-mini",
 "prompt_desc": "Genel Açıklama: İstanbul emniyet müdürlüğü için haberleri sınıflayacak bir asistansın. istanbul_ilceleri = [\"Adalar\", \"Arnavutköy\", \"Ataşehir\", \"Avcılar\", \"Bağcılar\", \"Bahçelievler\", \"Bakırköy\", \"Başakşehir\", \"Bayrampaşa\", \"Beşiktaş\", \"Beyoğlu\", \"Büyükçekmece\", \"Çatalca\", \"Çekmeköy\", \"Esenler\", \"Esenyurt\", \"Eyüp\", \"Fatih\", \"Gaziosmanpaşa\", \"Güngören\", \"Kadıköy\", \"Kağıthane\", \"Kartal\", \"Küçükçekmece\", \"Maltepe\", \"Pendik\", \"Sancaktepe\", \"Sarıyer\", \"Silivri\", \"Sultanbeyli\", \"Sultangazi\", \"Şişli\", \"Şile\", \"Tuzla\", \"Ümraniye\", \"Üsküdar\", \"Zeytinburnu\"]. Faaliyet Listesi: ['Trafik Denetleme Haberleri', 'Terörle Mücadele Haberleri', 'Siber Suç Haberleri', 'Narkotik Haberleri', 'Mali Suç Haberleri', 'Kaçakçılık Haberleri', 'Çevik Kuvvet Haberleri', 'Destek Hizmetleri Haberleri', 'Asayiş haberleri', 'Organize Suçlarla Mücadele Haberleri', 'Göçmen Haberleri', 'Toplumsal Olaylara Müdahale Haberleri', 'Spor Haberleri', 'Kurumsal Haberler']. Verilen haberi; Basın İçeriği, Faaliyet Alanı, Yorum ve Kategori kriterlerine göre sınıfla.\n1. Basın İçeriği: Haberin İstanbul emniyet müdürlüğü ile ilgili olup olmadığını ifade eder. \n– Evet: haber, İstanbul emniyet müdürlüğünü ilgilendiren bir haberdir. \n– Hayır: İstanbul emniyet müdürlüğünü ilgilendirmeyen bir haberdir. \n2. Faaliyet Alanı: Haberin genel konusunun kategorisidir. \n– Trafik Denetleme Haberleri: Trafik suçları, trafik kazaları, trafik denetimleri, trafik düzenlemeleri bu kapsamdadır. (Trafik kazası, trafik cezası) \n– Terörle Mücadele Haberleri: Terör örgütlerine karşı yürütülen operasyonlar, gözaltılar, tutuklamalar ve güvenlik önlemleri gibi terörle mücadele faaliyetlerini kapsayan haberler bu kategori altında sınıflandırılır. \n– Siber Suç Haberleri: İstanbul Emniyetinin internet ve dijital platformlar üzerinden gerçekleştirilen yasa dışı faaliyetler, dolandırıcılık, veri ihlali, kimlik hırsızlığı, siber saldırılar, siber zorbalık gibi suçlara karşı yürüttüğü operasyonlar ve soruşturmaları kapsayan haberler bu kategori altında sınıflandırılır. \n– Narkotik Haberleri: Uyuşturucu madde ticareti, kullanımı, üretimi ve dağıtımı ile mücadele etmek amacıyla yürüttüğü operasyonlar, gözaltılar, tutuklamalar ve ele geçirilen maddelerle ilgili haberler bu kategori altında sınıflandırılır. \n– Mali Suç Haberleri: İstanbul Emniyetinin finansal dolandırıcılık, kara para aklama, vergi kaçakçılığı, sahtecilik ve diğer mali suçlara karşı yürüttüğü operasyonlar, soruşturmalar ve yakalamalarla ilgili haberler bu kategori altında sınıflandırılır. \n– Kaçakçılık Haberleri: Yasa dışı mal, ürün veya hizmetlerin ticareti, taşınması ve dağıtımıyla mücadele etmek amacıyla yürüttüğü operasyonlar, soruşturmalar ve yakalamalarla ilgili haberler bu kategori altında sınıflandırılır. \n– Çevik Kuvvet Haberleri: Toplumsal olaylara müdahale eden, kamu düzenini sağlamak ve korumak amacıyla görev yapan Çevik Kuvvet ekiplerinin katıldığı operasyonlar, protesto ve gösterilere müdahale, büyük çaplı etkinliklerde alınan güvenlik önlemleri gibi haberler bu kategori altında sınıflandırılır. \n– Destek Hizmetleri Haberleri: Lojistik, araç ve gereç temini, personel desteği, eğitim, sağlık hizmetleri ve diğer destek faaliyetleriyle ilgili haberler bu kategori altında sınıflandırılır. \n– Asayiş Haberleri: Genel kamu düzenini ve güvenliğini sağlamaya yönelik gerçekleştirdiği operasyonlar, devriye faaliyetleri, hırsızlık, gasp, cinayet, kavga gibi suçların önlenmesi ve aydınlatılmasıyla ilgili haberler bu kategori altında sınıflandırılır. \n– Organize Suçlarla Mücadele Haberleri: Organize suç örgütlerine yönelik yürüttüğü operasyonlar, bu örgütlerin çökertilmesi, liderlerinin ve üyelerinin yakalanması, yasadışı faaliyetlerinin engellenmesi ve soruşturulmasıyla ilgili haberler bu kategori altında sınıflandırılır. \n– Göçmen Haberleri: Yasa dışı göçmen kaçakçılığı, insan ticaretiyle mücadelede, düzensiz göç, düzensiz göçmen haberleri bu kapsamdadır. \n– Toplumsal Olaylara Müdahale Haberleri: Toplum huzurunu bozan ve kamu düzenini tehdit eden toplumsal olaylara müdahale etmek, özellikle kitlesel protestolar, gösteriler, yürüyüşler, grevler, büyük spor etkinlikleri gibi halkın toplu olarak bulunduğu etkinliklerde asayişi sağlamak, şiddet ve vandalizmi önlemek amaçlı haberler bu kapsamdadır. \n– Spor Haberleri: Spor etkinliklerinin güvenliğini sağlamak, olayların huzur ve güven içinde geçmesini temin etmek ve taraftarlar arasında yaşanabilecek şiddet olaylarını önlemek amacıyla faaliyet gösteren emniyet birimidir. Bu şube, özellikle futbol maçları, basketbol maçları, ulusal ve uluslararası spor organizasyonları gibi büyük ölçekli spor etkinliklerinin güvenliğini sağlamakla yükümlüdür. \n– Kurumsal Haberler: Kurum faaliyetleri, başarıları, gelişmeleri, atamaları gibi önemli olayları hakkında yayımlanan haberlerdir. \n3. Yorum: Haber içeriğinin İstanbul emniyet müdürlüğü açısından okuyucuda bıraktığı duygu durumu. \n– NEGATİF: Haber, İstanbul emniyet müdürlüğü açısından genel olarak olumsuzluk içerir. \n– POZİTİF: Haber metni İstanbul emniyet müdürlüğü açısından genel olarak olumludur. \n– NÖTR: Haber genel olarak bilgilendirici, yorum içermeyen, tarafsız bilgilendirme yapar. \n4. Kategori: Haberin geçtiği İstanbul ilçesi. \n5. Konu: İstanbul emniyeti açısından konuyu anlatan en iyi başlığı yaz. (maksimum 7 kelime). Formatı; “istanbul_ilceleri - Konu” olacak şekilde yaz. Örnek: Kadıköy - trafik magandaları kameraya yansıdı.",
 "tools": {
   "Basın İçeriği": {
     "description": "Haberde İstanbul emniyet müdürlüğünün olup olmadığını ifade eder.",
     "enum": [
       "Evet",
       "Hayır"
     ],
     "type": "string"
   },
   "Faaliyet Alanı": {
     "description": "Bu alan haberin genel konusunun kategorisidir.",
     "enum": [
       "Trafik Denetleme Haberleri",
       "Terörle Mücadele Haberleri",
       "Siber Suç Haberleri",
       "Narkotik Haberleri",
       "Mali Suç Haberleri",
       "Kaçakçılık Haberleri",
       "Çevik Kuvvet Haberleri",
       "Destek Hizmetleri Haberleri",
       "Asayiş Haberleri",
       "Organize Suçlarla Mücadele Haberleri",
       "Göçmen Haberleri",
       "Toplumsal Olaylara Müdahale Haberleri",
       "Spor Haberleri",
       "Kurumsal Haberler",
       "Diğer Haberler"
     ],
     "type": "string"
   },
   "Yorum": {
     "description": "Haber içeriğinin İstanbul emniyet müdürlüğü açısından okuyucuda bıraktığı duygu durumu.",
     "enum": [
       "NEGATİF",
       "NÖTR",
       "POZİTİF"
     ],
     "type": "string"
   },
   "Kategori": {
     "description": "Haberin geçtiği İstanbul ilçesi.",
     "enum": [
       "Adalar",
       "Arnavutköy",
       "Ataşehir",
       "Avcılar",
       "Bağcılar",
       "Bahçelievler",
       "Bakırköy",
       "Başakşehir",
       "Bayrampaşa",
       "Beşiktaş",
       "Beyoğlu",
       "Büyükçekmece",
       "Çatalca",
       "Çekmeköy",
       "Esenler",
       "Esenyurt",
       "Eyüp",
       "Fatih",
       "Gaziosmanpaşa",
       "Güngören",
       "Kadıköy",
       "Kağıthane",
       "Kartal",
       "Küçükçekmece",
       "Maltepe",
       "Pendik",
       "Sancaktepe",
       "Sarıyer",
       "Silivri",
       "Sultanbeyli",
       "Sultangazi",
       "Şişli",
       "Şile",
       "Tuzla",
       "Ümraniye",
       "Üsküdar",
       "Zeytinburnu",
       "İstanbul (Haber tüm İstanbul'u kapsadığı ve spesifik bir ilçe belirtilmedi)",
       "İstanbul Dışı Bir Yer"
     ],
     "type": "string"
   },
   "Konu": {
     "description": "İstanbul emniyeti açısından konuyu anlatan en iyi başlığı yaz. (maksimum 7 kelime).",
     "type": "string"
   }
 }
}

bu bir ornek mesela bu gptye gore aam biz ollamaya gore ayarlayacagiz. ayrica kv cacheler arayuz uzerinden ozel olarak olsuturulabilmeli ve kisi istedigi kv cacehe ile gondererek modelin hizindan ve veriminden tasarruf edebilmeli. soyle dusun bir cok farkli sektor var hepsinin kendi kategori alanlari felan var o yuzden kullanici kendi kv cachelerini yaratip isteklerini ona gore ayarlayabilmeli ve cok fazla haber oldugu icin bunu en hizli sekilde elde edebilmeliyiz modeli hizlandiracak yontemleri kullanabilirsin bence kv cache cok mantikli veya quantize bir model kullanmakta 