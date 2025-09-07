import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from utils.chart_generator import ChartGenerator

class RootAgent:
    """
   EĞER CHAT SORUSU/SELAMLAŞMAYSA:
{"success": true, "command_type": "chat", "message": "Kullanıcıya yardımcı yanıt buraya"}

CHAT YANIT ÖRNEKLERİ:
- "Selam" → "Selam! Ben Vestel şikayet analiz sisteminizim. Size nasıl yardımcı olabilirim?"
- "Sen kimsin?" → "Ben Vestel şikayetlerini analiz eden bir AI asistanıyım. Şikayet verilerini toplar, kategorilere ayırır ve size analiz sonuçları sunarım."
- "Nasılsın?" → "İyiyim, teşekkürler! Vestel şikayet analizi için buradayım."
- "Ne yapıyorsun?" → "Vestel şikayetlerini web'den topluyorum, kategorilendiriyorum ve size detaylı analizler sunuyorum."oot Agent - Ana kontrol merkezi (LLM Destekli)
    - Doğal dilde yazılan komutları LLM ile analiz eder
    - Diğer agentları koordine eder
    - Sonuçları birleştirir
    """
    
    def __init__(self):
        self.chart_generator = ChartGenerator()
        
        # LLM client'ı import et
        from utils.llm_client import LLMClient
        self.llm_client = LLMClient()
        
        # Database manager'ı import et (tarih aralığı için)
        from database_manager import DatabaseManager
        self.db_manager = DatabaseManager()
    
    def process_request(self, user_prompt: str, data_agent, analysis_agent) -> Dict:
        """
        Ana işlem fonksiyonu - Hem chat hem analiz isteklerini karşılar
        1. Komutu LLM ile analiz et (chat mi, analiz mi?)
        2. Chat ise -> Direkt yanıt döndür
        3. Analiz ise -> Veritabanını güncelle, analiz yap, sonuç üret
        """
        try:
            command_info = self._parse_command_with_llm(user_prompt)
            if not command_info["success"]:
                return command_info
            
            if command_info.get("command_type") == "chat":
                return {
                    "success": True,
                    "request_type": "chat",
                    "message": command_info.get("message", "Chat yanıtı alınamadı")
                }
            
            update_result = data_agent.ensure_database_updated(command_info)
            if not update_result["success"]:
                return {
                    "success": False,
                    "request_type": "analysis",
                    "error": f"Veritabanı güncellenemedi: {update_result['error']}"
                }
            
            data_result = data_agent.get_data_for_analysis(
                command_info["command_type"], 
                command_info["parameters"]
            )
            
            if not data_result["success"]:
                return {
                    "success": False,
                    "error": f"Veri hazırlanamadı: {data_result['error']}"
                }
            
            if data_result.get("uncategorized_count", 0) == 0:
                return self._generate_statistics_only(data_agent, command_info, data_result)
            
            analysis_result = analysis_agent.analyze_complaints(
                data_result["jsonl_data"],
                data_result.get("complaint_ids", [])
            )
            
            if not analysis_result["success"]:
                return {
                    "success": False,
                    "error": f"Analiz hatası: {analysis_result['error']}"
                }
            
            if analysis_result.get("analysis_assignments"):
                save_result = data_agent.save_analysis(analysis_result["analysis_assignments"])
                if not save_result["success"]:
                    return {
                        "success": False,
                        "error": f"Analiz kaydetme hatası: {save_result['error']}"
                    }
            
            stats_result = self._generate_final_statistics(data_agent, analysis_result, data_result)
            
            response = {
                "success": True,
                "command_info": command_info,
                "update_result": update_result,
                "data_result": data_result,
                "analysis_result": analysis_result,
                "statistics": stats_result,
                "request_type": "analysis"
            }
            
            if stats_result.get("success"):
                response["category_chart_path"] = stats_result.get("category_chart_path")
                response["reason_chart_path"] = stats_result.get("reason_chart_path")
                response["category_stats"] = stats_result.get("category_stats", {})
                response["reason_stats"] = stats_result.get("reason_stats", {})
            
            return response
            
        except Exception as e:
            return {
                "success": False,
                "request_type": "analysis",
                "error": str(e)
            }
    
    def _parse_command_with_llm(self, prompt: str) -> Dict:
        """LLM ile kullanıcı komutunu analiz et"""
        try:
            # Bugünün tarihini al
            today = datetime.now()
            
            # Database'deki mevcut tarih aralığını al
            date_range_info = self.db_manager.get_data_date_range()
            earliest_date = date_range_info.get("earliest")
            latest_date = date_range_info.get("latest")
            
            # Database tarih bilgisi için string hazırla
            db_info = ""
            if earliest_date and latest_date:
                db_info = f"""
VERİTABANI TARİH BİLGİSİ:
- En eski şikayet: {earliest_date}
- En yeni şikayet: {latest_date}
- Mevcut yıl: 2025 (tüm veriler 2025 yılına ait)

NOT: Kullanıcı "ağustos ayı" derse 2025 Ağustos'u kastet ediyor.
NOT: Kullanıcı "mart ayı" derse 2025 Mart'ı kastet ediyor.
NOT: Yıl belirtilmezse her zaman 2025 yılını kullan."""
            else:
                db_info = "VERİTABANI TARİH BİLGİSİ: Tarih bilgisi alınamadı."
            
            llm_prompt = f"""
Sen bir Vestel şikayet analiz sistemi uzmanısın. İki tür işlem yapabilirsin:

1. 💬 CHAT: Sistem hakkında soru-cevap veya kısa selamlaşma
2. 🔍 ANALİZ: Veri analizi komutları

🚫 GUARDRAIL - KABUL ETMEDİĞİN SORULAR:
- Detaylı programlama soruları (kod yazma, debugging)
- Matematik problemleri çözme
- Genel ansiklopedi soruları
- Bu sistem dışındaki teknik konular
- Çok uzun kişisel konuşmalar (kısa sohbet OK)

✅ CHAT SORULARI (command_type: "chat"):
- Selam, merhaba, iyi günler, nasılsın, günaydın, iyi akşamlar (selamlaşmalar)
- Sen kimsin? Ne yapıyorsun? Amacın nedir? (sistem tanıtımı)
- Bu sistem nasıl kullanılır?
- Hangi komutları verebilirim?
- Sistemin özellikleri nelerdir?
- Vestel şikayet sistemi hakkında genel sorular
- Teşekkür ederim, sağol, eyvallah (nezaket ifadeleri)
- Nasıl çalışıyorsun? (sistem işleyişi hakkında)

✅ ANALİZ KOMUTLARI (command_type: analiz türü):
- Vestel şikayet verilerini analiz et
- Şikayet kategori dağılımlarını göster
- Belirli tarih aralığındaki şikayetleri analiz et
- Şikayet trendlerini analiz et

EĞER KULLANICI KOMUTU SİSTEM DIŞINDAKİ CİDDİ BİR KONUYSA:
{{"success": false, "error": "Bu konuda size yardımcı olamam. Vestel şikayet analizi veya sistemi hakkında soru sorabilirsiniz.", "command_type": "invalid"}}

EĞER CHAT SORUSU/SELAMLAŞMAYSA:
{{"success": true, "command_type": "chat", "message": "Kullanıcıya yardımcı yanıt buraya"}}

BUGÜNÜN TARİHİ VE SAATİ: {today.strftime('%Y-%m-%d %H:%M:%S')} ({today.strftime('%A')})

{db_info}

KULLANICI KOMUTU: "{prompt}"

ÖNCE KONTROL ET: Bu komut Vestel şikayet analizi ile ilgili mi?
- EĞER DEĞİLSE: Yukarıdaki error mesajını döndür
- EĞER İLGİLİSE: Aşağıdaki analizi yap

DESTEKLENEN KOMUT TİPLERİ:
1. last_count: Son N şikayeti analiz et
2. date_range: Belirli tarih aralığını analiz et  
3. month: Belirli ayı analiz et
4. hours_back: Son N saati analiz et (SAAT CİNSİNDEN)
5. days_back: Son N günü analiz et (GÜN CİNSİNDEN)

ZAMAN ANLAMA KURALLARI:
- "son 24 saat", "son 6 saat", "son 2 saat" → hours_back (SAATLİK ANALİZ)
- "son 3 gün", "son 1 hafta", "son 2 gün" → days_back (GÜNLÜK ANALİZ)  
- "saat" kelimesi geçiyorsa hours_back, "gün/hafta" geçiyorsa days_back
- DİKKAT: "24 saat" = 1 gün değil, tam 24 saatlik period!
- "ağustos ayı", "mart ayı" gibi ay isimleri → month (2025 yılında)

ÖRNEKLER VE ÇIKTILAR:
- "Son 24 saati analiz et" → {{"success": true, "command_type": "hours_back", "parameters": {{"hours": 24}}, "description": "Son 24 saat analizi"}}
- "Son 6 saat" → {{"success": true, "command_type": "hours_back", "parameters": {{"hours": 6}}, "description": "Son 6 saat analizi"}}
- "Son 2 saati" → {{"success": true, "command_type": "hours_back", "parameters": {{"hours": 2}}, "description": "Son 2 saat analizi"}}
- "Son 2 günü analiz et" → {{"success": true, "command_type": "days_back", "parameters": {{"days": 2}}, "description": "Son 2 gün analizi"}}
- "Son 1 hafta" → {{"success": true, "command_type": "days_back", "parameters": {{"days": 7}}, "description": "Son 7 gün analizi"}}
- "Son 10 şikayeti analiz et" → {{"success": true, "command_type": "last_count", "parameters": {{"count": 10}}, "description": "Son 10 şikayet analizi"}}
- "Ağustos ayını analiz et" → {{"success": true, "command_type": "month", "parameters": {{"year": 2025, "month": 8}}, "description": "2025 Ağustos analizi"}}
- "Mart ayı" → {{"success": true, "command_type": "month", "parameters": {{"year": 2025, "month": 3}}, "description": "2025 Mart analizi"}}

GÖREV:
Kullanıcı komutunu analiz ederek SADECE JSON formatında yanıt ver. Başka hiçbir şey yazma.

{{"success": true, "command_type": "hours_back", "parameters": {{"hours": 24}}, "description": "Son 24 saat analizi"}}"""

            response = self.llm_client.generate_content(llm_prompt)
            
            if not response or not response.strip():
                return self._parse_command_fallback(prompt)
            
            import json
            try:
                cleaned_response = response.strip()
                if cleaned_response.startswith('```'):
                    lines = cleaned_response.split('\n')
                    cleaned_response = '\n'.join(line for line in lines if not line.startswith('```'))
                    cleaned_response = cleaned_response.strip()
                
                result = json.loads(cleaned_response)
                
                if result.get("command_type") == "days_back" and result.get("success"):
                    days = result["parameters"]["days"]
                    end_date = today
                    start_date = today - timedelta(days=days-1)
                    
                    result = {
                        "success": True,
                        "command_type": "date_range",
                        "parameters": {
                            "start_date": start_date.strftime('%Y-%m-%d'),
                            "end_date": end_date.strftime('%Y-%m-%d')
                        },
                        "description": f"Son {days} gün analizi ({start_date.strftime('%Y-%m-%d')} - {end_date.strftime('%Y-%m-%d')})"
                    }
                
                # Eğer hours_back ise tarih-saat aralığına çevir
                elif result.get("command_type") == "hours_back" and result.get("success"):
                    hours = result["parameters"]["hours"]
                    end_datetime = today
                    start_datetime = today - timedelta(hours=hours)
                    
                    result = {
                        "success": True,
                        "command_type": "datetime_range",
                        "parameters": {
                            "start_datetime": start_datetime.strftime('%Y-%m-%d %H:%M:%S'),
                            "end_datetime": end_datetime.strftime('%Y-%m-%d %H:%M:%S')
                        },
                        "description": f"Son {hours} saat analizi ({start_datetime.strftime('%Y-%m-%d %H:%M')} - {end_datetime.strftime('%Y-%m-%d %H:%M')})"
                    }
                
                return result
                
            except json.JSONDecodeError as e:
                return self._parse_command_fallback(prompt)
                
        except Exception as e:
            return self._parse_command_fallback(prompt)

    def _parse_command_fallback(self, prompt: str) -> Dict:
        """Fallback: Basit pattern matching ile komut analizi"""
        prompt_lower = prompt.lower().strip()
        today = datetime.now()
        
        try:
            # Son N saat pattern'i
            hour_patterns = [
                r'son\s+(\d+)\s+saat',
                r'(\d+)\s+saat',
                r'son\s+(\d+)\s+saati'
            ]
            
            for pattern in hour_patterns:
                match = re.search(pattern, prompt_lower)
                if match:
                    hours = int(match.group(1))
                    start_datetime = today - timedelta(hours=hours)
                    end_datetime = today
                    
                    return {
                        "success": True,
                        "command_type": "datetime_range",
                        "parameters": {
                            "start_datetime": start_datetime.strftime('%Y-%m-%d %H:%M:%S'),
                            "end_datetime": end_datetime.strftime('%Y-%m-%d %H:%M:%S')
                        },
                        "description": f"Son {hours} saat analizi ({start_datetime.strftime('%Y-%m-%d %H:%M')} - {end_datetime.strftime('%Y-%m-%d %H:%M')})"
                    }
            
            # Son N gün pattern'i
            day_patterns = [
                r'son\s+(\d+)\s+gün',
                r'(\d+)\s+gün', 
                r'son\s+(\d+)\s+günü'
            ]
            
            # Özel durum: "son günü" -> bugünkü verileri analiz et
            if 'son günü' in prompt_lower or 'son gün' in prompt_lower:
                # "son günü" dendiğinde bugünü analiz et
                return {
                    "success": True,
                    "command_type": "date_range", 
                    "parameters": {
                        "start_date": today.strftime('%Y-%m-%d'),
                        "end_date": today.strftime('%Y-%m-%d')
                    },
                    "description": f"Bugünkü analiz ({today.strftime('%Y-%m-%d')})"
                }
            
            for pattern in day_patterns:
                match = re.search(pattern, prompt_lower)
                if match:
                    days = int(match.group(1))
                    start_date = today - timedelta(days=days-1)
                    end_date = today
                    
                    return {
                        "success": True,
                        "command_type": "date_range",
                        "parameters": {
                            "start_date": start_date.strftime('%Y-%m-%d'),
                            "end_date": end_date.strftime('%Y-%m-%d')
                        },
                        "description": f"Son {days} gün analizi ({start_date.strftime('%Y-%m-%d')} - {end_date.strftime('%Y-%m-%d')})"
                    }
            
            # Son N şikayet pattern'i
            count_pattern = r'son\s+(\d+)\s+şikayet'
            count_match = re.search(count_pattern, prompt_lower)
            if count_match:
                count = int(count_match.group(1))
                return {
                    "success": True,
                    "command_type": "last_count",
                    "parameters": {"count": count},
                    "description": f"Son {count} şikayet analizi"
                }
            
            # Ay analizi pattern'i
            turkish_months = {
                'ocak': 1, 'şubat': 2, 'mart': 3, 'nisan': 4,
                'mayıs': 5, 'haziran': 6, 'temmuz': 7, 'ağustos': 8,
                'eylül': 9, 'ekim': 10, 'kasım': 11, 'aralık': 12
            }
            
            month_pattern = r'(\w+)\s+ay'
            month_match = re.search(month_pattern, prompt_lower)
            if month_match:
                month_name = month_match.group(1)
                if month_name in turkish_months:
                    current_year = datetime.now().year
                    month_num = turkish_months[month_name]
                    return {
                        "success": True,
                        "command_type": "month",
                        "parameters": {"year": current_year, "month": month_num},
                        "description": f"{month_name.title()} {current_year} analizi"
                    }
            
            # Tarih aralığı pattern'i
            date_pattern = r'(\d{4}-\d{2}-\d{2})\s+(\d{4}-\d{2}-\d{2})'
            date_match = re.search(date_pattern, prompt)
            if date_match:
                start_date = date_match.group(1)
                end_date = date_match.group(2)
                return {
                    "success": True,
                    "command_type": "date_range",
                    "parameters": {"start_date": start_date, "end_date": end_date},
                    "description": f"{start_date} - {end_date} arası analiz"
                }
            
            return {
                "success": False,
                "error": "Komut anlaşılamadı. Örnekler: 'Son 10 şikayeti analiz et', 'Son 2 günü analiz et', 'Mart ayını analiz et'"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Fallback analiz hatası: {e}"
            }
    
    def _generate_statistics_only(self, data_agent, command_info, data_result) -> Dict:
        """Sadece mevcut istatistikleri göster (yeni kategorileme yok)"""
        try:
            # Spesifik complaint ID'ler varsa onların istatistiklerini al
            if 'all_complaint_ids' in data_result:
                complaint_ids = data_result['all_complaint_ids']
                analysis_stats = data_agent.db_manager.get_final_analysis_stats_for_complaints(complaint_ids)
                category_stats = analysis_stats.get("categories", {})
                reason_stats = analysis_stats.get("reasons", {})
            else:
                # Fallback - bu duruma düşmemeli artık
                category_stats = {}
                reason_stats = {}
            
            # Grafikleri oluştur
            category_chart_path = None
            reason_chart_path = None
            
            # Kategori grafiği
            if category_stats:
                category_chart_path = self.chart_generator.create_category_chart(category_stats)
            
            # Sebep grafiği
            if reason_stats:
                reason_chart_path = self.chart_generator.create_reason_chart(reason_stats)
            
            return {
                "success": True,
                "command_info": command_info,
                "data_result": data_result,
                "category_stats": category_stats,
                "reason_stats": reason_stats,
                "category_chart_path": category_chart_path,
                "reason_chart_path": reason_chart_path,
                "new_categorizations": 0
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def _generate_final_statistics(self, data_agent, analysis_result, data_result) -> Dict:
        """Final istatistikleri ve grafik oluştur"""
        try:
            # Spesifik complaint IDs varsa, sadece onların istatistiklerini al
            if 'all_complaint_ids' in data_result:
                complaint_ids = data_result['all_complaint_ids']
                analysis_stats = data_agent.db_manager.get_final_analysis_stats_for_complaints(complaint_ids)
            else:
                # Bu duruma düşmemeli artık
                analysis_stats = {"categories": {}, "reasons": {}}
            
            # Grafikleri oluştur
            category_chart_path = None
            reason_chart_path = None
            
            category_stats = analysis_stats.get("categories", {})
            reason_stats = analysis_stats.get("reasons", {})
            
            # Kategori grafiği
            if category_stats:
                category_chart_path = self.chart_generator.create_category_chart(category_stats)
            
            # Sebep grafiği
            if reason_stats:
                reason_chart_path = self.chart_generator.create_reason_chart(reason_stats)
            
            return {
                "success": True,
                "category_stats": category_stats,
                "reason_stats": reason_stats,
                "category_chart_path": category_chart_path,
                "reason_chart_path": reason_chart_path,
                "new_analysis": len(analysis_result.get("analysis_assignments", []))
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }