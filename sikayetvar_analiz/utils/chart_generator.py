import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # GUI olmadan kullanım için
from typing import Dict, List
import os

class ChartGenerator:
    def __init__(self):
        # Türkçe karakter desteği
        plt.rcParams['font.family'] = ['DejaVu Sans']
    
    def create_category_chart(self, category_stats: Dict[str, int], save_path: str = "category_chart.png"):
        """Kategori istatistikleri için chart oluştur"""
        try:
            if not category_stats:
                return None
            
            return self._create_pie_chart(category_stats, save_path, "Şikayet Kategorileri Dağılımı")
                
        except Exception as e:
            return None

    def create_reason_chart(self, reason_stats: Dict[str, int], save_path: str = "reason_chart.png"):
        """Sebep istatistikleri için chart oluştur"""
        try:
            if not reason_stats:
                return None
            
            return self._create_pie_chart(reason_stats, save_path, "Şikayet Sebepleri Dağılımı")
                
        except Exception as e:
            return None
    
    def _create_pie_chart(self, stats: Dict[str, int], save_path: str, title: str):
        """Pasta grafik oluştur"""
        try:
            # Grafik boyutunu daha da büyüttük (16x12)
            plt.figure(figsize=(16, 12))
            
            categories = list(stats.keys())
            values = list(stats.values())
            
            # En büyük 8 kategoriyi al, geri kalanı "Diğer" olarak grupla
            if len(categories) > 8:
                # Mevcut "Diğer" kategorisini kontrol et
                existing_other = 0
                other_variations = ['Diğer', 'diğer', 'DIĞER', 'Diger', 'diger']
                
                # Diğer kategorilerini topla ve listeden çıkar
                filtered_categories = []
                filtered_values = []
                
                for cat, val in zip(categories, values):
                    if cat in other_variations:
                        existing_other += val
                    else:
                        filtered_categories.append(cat)
                        filtered_values.append(val)
                
                # En büyük 7'yi al (çünkü "Diğer" için 1 yer ayırıyoruz)
                if len(filtered_categories) > 7:
                    top_items = sorted(zip(filtered_categories, filtered_values), key=lambda x: x[1], reverse=True)[:7]
                    remaining_sum = sum([v for k, v in zip(filtered_categories, filtered_values) if k not in [item[0] for item in top_items]])
                    
                    categories = [item[0] for item in top_items] + ['Diğer']
                    values = [item[1] for item in top_items] + [remaining_sum + existing_other]
                else:
                    # 7'den az kategori varsa, sadece mevcut "Diğer"leri birleştir
                    if existing_other > 0:
                        categories = filtered_categories + ['Diğer']
                        values = filtered_values + [existing_other]
                    else:
                        categories = filtered_categories
                        values = filtered_values
            
            # Label'lara adet sayılarını ekle
            labels_with_counts = [f"{category} ({count})" for category, count in zip(categories, values)]
            
            # Renk paleti
            colors = plt.cm.Set3(range(len(categories)))
            
            # Pasta grafiği oluştur
            plt.pie(values, labels=labels_with_counts, autopct='%1.1f%%', colors=colors, startangle=90)
            
            # Başlığı çok daha yukarıda ve daha büyük fontla yerleştir
            plt.title(title, fontsize=22, fontweight='bold', pad=50)
            plt.axis('equal')
            
            # Alt ve üst boşlukları daha da artır
            plt.subplots_adjust(top=0.80, bottom=0.1)
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            plt.close()
            
            return save_path
            
        except Exception as e:
            return None