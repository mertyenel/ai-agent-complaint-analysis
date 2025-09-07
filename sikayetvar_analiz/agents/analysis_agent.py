import json
from typing import List, Dict, Optional
from utils.llm_client import LLMClient
from config import Config

class AnalysisAgent:
    """
    Analiz Agentı
    - JSONL verilerini LLM ile analiz eder
    - LLM'den JSONL çıktı alır
    - Sonuçları database'e kaydeder
    """
    
    def __init__(self):
        # LLM client'ı kendisi initialize etsin
        self.llm_client = LLMClient()
        self.categories = Config.CATEGORIES
        # Reason kategorileri sabit 10'lu liste
        self.reasons = [
            "Teknik Servis",
            "Kargo & Teslimat", 
            "Müşteri Hizmetleri",
            "Fiyat & Fatura",
            "Ürün Kalitesi",
            "Website & Uygulama",
            "İade & Değişim",
            "Satış & Mağaza",
            "Zaman & Süreç",
            "Diğer"
        ]
    
    def analyze_complaints(self, jsonl_data: str, complaint_ids: List[int] = None) -> Dict:
        """JSONL formatındaki şikayetleri analiz et ve kategorile"""
        try:
            if not jsonl_data or not jsonl_data.strip():
                return {
                    "success": True,
                    "analysis_assignments": [],
                    "message": "Analiz edilecek veri yok"
                }
            
            
            # JSONL'i parse et ve göster
            complaints = []
            for line_num, line in enumerate(jsonl_data.strip().split('\n'), 1):
                if line.strip():
                    try:
                        complaint = json.loads(line)
                        complaints.append(complaint)
                    except json.JSONDecodeError as e:
                        continue
            
            if not complaints:
                return {
                    "success": False,
                    "error": "Geçerli şikayet verisi bulunamadı"
                }
            
            # LLM ile toplu analiz
            analysis_assignments = self._analyze_with_llm_batch(jsonl_data)
            
            if analysis_assignments:
                return {
                    "success": True,
                    "analysis_assignments": analysis_assignments,
                    "processed_count": len(analysis_assignments)
                }
            else:
                return {
                    "success": False,
                    "error": "Analiz başarısız - LLM yanıt vermedi"
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def _analyze_with_llm_batch(self, jsonl_input: str) -> List[Dict]:
        """LLM ile batch analiz - JSONL input, JSONL output"""
        try:
            # Kategorileri string olarak hazırla
            categories_str = "\n".join([f"- {cat}" for cat in self.categories])
            
            # Reason'ları string olarak hazırla  
            reasons_str = "\n".join([f"{i+1}. {reason}" for i, reason in enumerate(self.reasons)])
            
            prompt = f"""Sen bir Vestel ürün şikayet kategorilendirme uzmanısın. 

Aşağıdaki JSONL formatındaki şikayetleri analiz ederek her birini doğru kategoriye ata ve şikayet nedenini belirle.

GİRİŞ VERİSİ:
{jsonl_input}

MEVCUT KATEGORİLER (Vestel Ürünleri):
{categories_str}

ŞİKAYET NEDENLERİ:
{reasons_str}

GÖREV:
1. Her şikayetin başlık ve içeriğini analiz et
2. Şikayetin hangi Vestel ürününe ait olduğunu belirle (category)
3. Şikayetin nedenini belirle (reason) - yukarıdaki 10 nedeninden birini seç
4. SADECE aşağıdaki JSONL formatında çıktı ver:

ÇIKTI FORMATI (Her satır ayrı JSON objesi olacak):
{{"Complaint_ID": 1, "category": "Televizyon", "reason": "Teknik Servis"}}
{{"Complaint_ID": 2, "category": "Buzdolabı", "reason": "İade & Değişim"}}

ÖNEMLİ:
- Sadece yukarıdaki kategorilerden birini kullan (category)
- Sadece yukarıdaki 10 nedenden birini kullan (reason)  
- Her şikayet için kesinlikle category ve reason ata
- Başka hiçbir açıklama yapma
- Sadece JSONL formatında yanıt ver

CEVAP:"""

            response = self.llm_client.generate_content(prompt)
            
            # LLM çıktısını parse et
            analysis_assignments = self._parse_llm_response(response)
            
            return analysis_assignments
            
        except Exception as e:
            return []

    def _parse_llm_response(self, response: str) -> List[Dict]:
        """LLM'den gelen JSONL yanıtını parse et"""
        try:
            analysis_assignments = []
            lines = response.strip().split('\n')
            
            for line_num, line in enumerate(lines, 1):
                line = line.strip()
                if not line or line.startswith('```'):
                    continue
                
                try:
                    # JSON parse et
                    data = json.loads(line)
                    
                    # Gerekli alanları kontrol et
                    if 'Complaint_ID' in data and 'category' in data and 'reason' in data:
                        complaint_id = data['Complaint_ID']
                        category = data['category']
                        reason = data['reason']
                        
                        # Category validasyonu
                        if category not in self.categories:
                            category = self._find_closest_category(category)
                        
                        # Reason validasyonu
                        if reason not in self.reasons:
                            reason = self._find_closest_reason(reason)
                        
                        analysis_assignments.append({
                            "Complaint_ID": complaint_id,
                            "category": category,
                            "reason": reason
                        })
                    else:
                        pass
                        
                except json.JSONDecodeError as e:
                    continue
                except Exception as e:
                    continue
            
            return analysis_assignments
            
        except Exception as e:
            return []
    
    def _find_closest_reason(self, response_reason: str) -> str:
        """Yanıtta geçen reason ile en yakın gerçek reason'u bul"""
        response_lower = response_reason.lower()
        
        # Doğrudan eşleşme kontrol et (kısmi eşleşme dahil)
        for reason in self.reasons:
            if reason.lower() in response_lower or response_lower in reason.lower():
                return reason
        
        # Varsayılan reason
        return "Diğer"
    
    def _find_closest_category(self, response_category: str) -> str:
        """Yanıtta geçen kategori ile en yakın gerçek kategoriyi bul"""
        response_lower = response_category.lower()
        
        # Doğrudan eşleşme kontrol et (kısmi eşleşme dahil)
        for category in self.categories:
            if category.lower() in response_lower or response_lower in category.lower():
                return category
        
        # Varsayılan kategori
        return "Televizyon"