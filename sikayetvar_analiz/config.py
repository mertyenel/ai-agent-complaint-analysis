import os
from dotenv import load_dotenv

# .env dosyasını yükle
load_dotenv()

class Config:
    # API Keys
    GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
    
    # Database - Ana dizindeki tek veritabanı
    DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'sikayetvar.db')
    
    # Scrapy ayarları
    SCRAPY_PROJECT_PATH = os.path.join(os.path.dirname(__file__), 'sv_vestel')
    
    # Kategoriler
    CATEGORIES = [
        "Akıllı Priz", "Akıllı Saat", "Akıllı Tahta", "Akıllı Tartı", "Ankastre Fırın",
        "Ankastre Ocak", "Ankastre Set", "Aspiratör", "Bilgisayar", "Blender", "Blender Seti",
        "Buhar Kazanlı Ütü", "Buharlı Ütü", "Bulaşık Makinesi", "Buzdolabı", "Çamaşır Makinesi",
        "Çay Makinesi", "Çeyiz Paketi", "Davlumbaz", "Derin Dondurucu", "Dikey Süpürge",
        "Doğrayıcı", "Elektrikli Süpürge", "Espresso Makinesi", "Fırın", "Filtre Kahve Makinesi",
        "Hamur Yoğurma Makinesi", "Hoparlör", "Kahve Makinesi", "Kettle", "Kıyma Makinesi",
        "Klima", "Kombi", "Kulaklık", "Kumanda", "Kurutma Makinesi", "Kurutmalı Çamaşır Makinesi",
        "Mikrodalga", "Mikser", "Narenciye Sıkacağı", "Ocak", "Robot Süpürge", "Saç Kurutma Makinesi",
        "Semaver", "Ses Sistemi", "Set Üstü Ocak", "Su Arıtma Cihazı", "Su Sebili", "Süpürge",
        "Şarj İstasyonu", "Tablet", "Televizyon", "Termosifon", "Tost Makinesi",
        "Türk Kahve Makinesi", "Uydu Alıcısı", "Ütü", "Vakum Makinesi", "Vantilatör"
    ]
    
    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    
    @classmethod
    def validate(cls):
        """Ayarları doğrula"""
        if not cls.GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY .env dosyasında tanımlanmalı!")
        return True