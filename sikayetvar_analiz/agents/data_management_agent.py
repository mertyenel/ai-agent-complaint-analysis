import subprocess
import json
import os
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from config import Config

class DataManagementAgent:
    """
    Veri Yönetim Agentı
    - Scrapy komutlarını çalıştırır
    - Veritabanını günceller  
    - Root Agent için veri hazırlar
    """
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.scrapy_project_path = Config.SCRAPY_PROJECT_PATH
    
    def ensure_database_updated(self, command_info: Optional[Dict] = None) -> Dict:
        """Veritabanını incremental update ile güncelle"""
        try:
            result = self.update_database_incremental()
            
            if result["success"]:
                new_count = result.get("new_records", 0)
                return {
                    "success": True,
                    "message": "Veritabanı güncellendi", 
                    "new_records": new_count
                }
            else:
                return result
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_data_for_analysis(self, command_type: str, parameters: Dict) -> Dict:
        """
        Root Agent'tan gelen komuta göre analiz için veri hazırla
        """
        try:
            
            if command_type == "last_count":
                return self._get_last_n_complaints(parameters["count"])
            elif command_type == "date_range":
                return self._get_complaints_by_date_range(
                    parameters["start_date"], 
                    parameters["end_date"]
                )
            elif command_type == "month":
                return self._get_complaints_by_month(
                    parameters["year"], 
                    parameters["month"]
                )
            elif command_type == "all":
                # Belirli complaint ID'ler için veri al
                if "complaint_ids" in parameters:
                    return self._get_complaints_by_ids(parameters["complaint_ids"])
                else:
                    return {
                        "success": False,
                        "error": "complaint_ids parametresi gerekli"
                    }
            else:
                return {
                    "success": False,
                    "error": f"Bilinmeyen komut tipi: {command_type}"
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def _get_last_n_complaints(self, count: int) -> Dict:
        """Son N şikayeti getir ve kategorisiz olanları filtrele"""
        try:
            # Son N şikayeti al (tarih olarak en yakın)
            complaints, complaint_ids = self.db_manager.get_complaints_by_count(count)
            
            if not complaints:
                return {
                    "success": True,
                    "data_type": "last_count", 
                    "total_requested": count,
                    "total_found": 0,
                    "uncategorized_count": 0,
                    "message": "Hiç şikayet bulunamadı"
                }
            
            
            # Bu specific ID'ler arasında kategorisiz olanları bul
            uncategorized = self.db_manager.get_uncategorized_complaints(complaint_ids)
            
            
            if uncategorized:
                # JSONL formatında hazırla
                jsonl_data = self._prepare_jsonl_data(uncategorized)
                
                return {
                    "success": True,
                    "data_type": "last_count",
                    "total_requested": count,
                    "total_found": len(complaints),
                    "uncategorized_count": len(uncategorized),
                    "jsonl_data": jsonl_data,
                    "complaint_ids": [c["Complaint_ID"] for c in uncategorized],
                    "all_complaint_ids": complaint_ids  # Tüm son 5'in ID'si
                }
            else:
                return {
                    "success": True,
                    "data_type": "last_count",
                    "total_requested": count,
                    "total_found": len(complaints),
                    "uncategorized_count": 0,
                    "message": "Son 5 şikayet zaten kategorize edilmiş",
                    "all_complaint_ids": complaint_ids  # Tüm son 5'in ID'si
                }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _get_complaints_by_date_range(self, start_date: str, end_date: str) -> Dict:
        """Tarih aralığındaki şikayetleri getir"""
        try:
            complaints, complaint_ids = self.db_manager.get_complaints_by_date_range(start_date, end_date)
            
            if not complaints:
                return {
                    "success": True,
                    "data_type": "date_range",
                    "date_range": f"{start_date} - {end_date}",
                    "total_found": 0,
                    "uncategorized_count": 0,
                    "message": "Bu tarih aralığında şikayet bulunamadı"
                }
            
            uncategorized = self.db_manager.get_uncategorized_complaints(complaint_ids)
            
            if uncategorized:
                jsonl_data = self._prepare_jsonl_data(uncategorized)
                
                return {
                    "success": True,
                    "data_type": "date_range",
                    "date_range": f"{start_date} - {end_date}",
                    "total_found": len(complaints),
                    "uncategorized_count": len(uncategorized),
                    "jsonl_data": jsonl_data,
                    "complaint_ids": [c["Complaint_ID"] for c in uncategorized],
                    "all_complaint_ids": complaint_ids
                }
            else:
                return {
                    "success": True,
                    "data_type": "date_range", 
                    "date_range": f"{start_date} - {end_date}",
                    "total_found": len(complaints),
                    "uncategorized_count": 0,
                    "message": "Tüm şikayetler zaten kategorize edilmiş",
                    "all_complaint_ids": complaint_ids
                }
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _get_complaints_by_month(self, year: int, month: int) -> Dict:
        """Belirli aya ait şikayetleri getir"""
        try:
            # Ay başı ve sonu tarihlerini hesapla
            start_date = f"{year}-{month:02d}-01"
            
            # Sonraki ayın ilk gününü hesapla
            if month == 12:
                next_month = 1
                next_year = year + 1
            else:
                next_month = month + 1
                next_year = year
            
            # Ayın son günü
            import calendar
            last_day = calendar.monthrange(year, month)[1]
            end_date = f"{year}-{month:02d}-{last_day}"
            
            return self._get_complaints_by_date_range(start_date, end_date)
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _prepare_jsonl_data(self, complaints: List[Dict]) -> str:
        """Şikayetleri JSONL formatında hazırla"""
        jsonl_lines = []
        for complaint in complaints:
            jsonl_line = {
                "Complaint_ID": complaint["Complaint_ID"],
                "full_comment": complaint["full_comment"],
                "ref_url": complaint["ref_url"],
                "title": complaint["title"],
                "date": complaint["date"]
            }
            jsonl_lines.append(json.dumps(jsonl_line, ensure_ascii=False))
        
        return "\n".join(jsonl_lines)
    
    def save_analysis(self, analysis_assignments: List[Dict]) -> Dict:
        """Analiz Agent'tan gelen analiz atamalarını kaydet"""
        try:
            saved_count = self.db_manager.insert_analysis(analysis_assignments)
            
            return {
                "success": True,
                "saved_count": saved_count,
                "message": f"{saved_count} analiz ataması kaydedildi"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def update_database_incremental(self) -> Dict:
        """Database'i incremental olarak güncelle"""
        try:
            existing_refs = self.db_manager.get_all_ref_urls()
            result = self._run_spider_incremental(existing_refs)
            
            if result.get('success'):
                new_count = result.get('new_count', 0)
                return {
                    'success': True,
                    'new_count': new_count,
                    'duplicate_count': result.get('duplicate_count', 0),
                    'new_complaint_ids': result.get('new_complaint_ids', []),
                    'message': f'{new_count} yeni şikayet eklendi'
                }
            else:
                return {
                    'success': False,
                    'error': result.get('error', 'Spider hatası'),
                    'new_count': 0
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'new_count': 0
            }

    def _run_spider_incremental(self, existing_refs: set) -> Dict:
        """Spider'ı incremental modda çalıştır"""
        try:
            # Temporary file ile existing refs'i spider'a geç
            import tempfile
            import json
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(list(existing_refs), f)
                refs_file = f.name
            
            try:
                cmd = [
                    'scrapy', 'crawl', 'vestel_last',
                    '-a', f'incremental=true',
                    '-a', f'existing_refs_file={refs_file}',
                    '-a', 'start_page=1'
                ]
                
                result = subprocess.run(
                    cmd,
                    cwd=self.scrapy_project_path,
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                
                if result.returncode == 0:
                    return self._parse_spider_output(result.stdout)
                else:
                    return {
                        'success': False,
                        'error': f'Spider failed: {result.stderr}'
                    }
                    
            finally:
                # Temp file'ı temizle
                try:
                    os.unlink(refs_file)
                except:
                    pass
                    
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': 'Spider timeout'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def _parse_spider_output(self, output: str) -> Dict:
        """Spider çıktısından sonuçları parse et"""
        try:
            new_count = 0
            duplicate_count = 0
            
            for line in output.split('\n'):
                if 'items_scraped_count' in line:
                    import re
                    match = re.search(r'items_scraped_count.*?(\d+)', line)
                    if match:
                        new_count = int(match.group(1))
                        
                elif 'DUPLICATE_FOUND' in line:
                    duplicate_count += 1
                    
                elif 'STOPPING' in line and 'duplicate' in line.lower():
                    break
            
            return {
                'success': True,
                'new_count': new_count,
                'duplicate_count': duplicate_count,
                'new_complaint_ids': []
            }
            
        except Exception as e:
            return {
                'success': True,
                'new_count': 0,
                'duplicate_count': 0,
                'new_complaint_ids': []
            }
    
    def _get_complaints_by_ids(self, complaint_ids: List[int]) -> Dict:
        """Belirli ID'lere göre şikayetleri getir"""
        try:
            if not complaint_ids:
                return {
                    "success": True,
                    "data_type": "by_ids",
                    "total_found": 0,
                    "uncategorized_count": 0,
                    "jsonl_data": "",
                    "all_complaint_ids": [],
                    "message": "Hiç şikayet ID'si belirtilmedi"
                }
            
            # Belirtilen ID'lerdeki şikayetleri al
            complaints = []
            for complaint_id in complaint_ids:
                complaint_data = self.db_manager.get_complaint_by_id(complaint_id)
                if complaint_data:
                    complaints.append(complaint_data)
            
            if not complaints:
                return {
                    "success": True,
                    "data_type": "by_ids",
                    "total_found": 0,
                    "uncategorized_count": 0,
                    "jsonl_data": "",
                    "all_complaint_ids": [],
                    "message": "Belirtilen ID'lerde şikayet bulunamadı"
                }
            
            # JSONL formatına dönüştür
            jsonl_data = self._prepare_jsonl_data(complaints)
            
            return {
                "success": True,
                "data_type": "by_ids",
                "total_found": len(complaints),
                "uncategorized_count": len(complaints),  # Hepsi analiz edilecek
                "jsonl_data": jsonl_data,
                "all_complaint_ids": complaint_ids,
                "complaint_ids": complaint_ids
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }