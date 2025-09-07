from flask import Flask, render_template, request, jsonify, send_file
import os
import base64
from datetime import datetime
import threading
import time

from config import Config
from database_manager import DatabaseManager
from agents.root_agent import RootAgent
from agents.data_management_agent import DataManagementAgent
from agents.analysis_agent import AnalysisAgent

app = Flask(__name__)

db_manager = None
root_agent = None
data_agent = None
analysis_agent = None
current_task = None
task_results = {}

def initialize_system():
    """Sistem bileşenlerini başlat"""
    global db_manager, root_agent, data_agent, analysis_agent
    
    try:
        Config.validate()
        db_manager = DatabaseManager()
        root_agent = RootAgent()
        data_agent = DataManagementAgent(db_manager)
        analysis_agent = AnalysisAgent()
        return True
    except Exception as e:
        return False

def get_chart_base64(chart_path):
    """Chart dosyasını base64'e çevir"""
    try:
        if not chart_path or not os.path.exists(chart_path):
            return None
            
        with open(chart_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode('utf-8')
            
    except Exception as e:
        return None

def process_request_async(prompt, task_id):
    """Asenkron istek işleme"""
    global task_results
    
    try:
        result = root_agent.process_request(prompt, data_agent, analysis_agent)
        request_type = result.get('request_type', 'analysis')
        
        if request_type == 'chat':
            task_results[task_id] = {
                'status': 'completed',
                'success': result.get('success', False),
                'type': 'chat',
                'response': result.get('message', 'Yanıt alınamadı'),
                'timestamp': datetime.now().isoformat()
            }
            
        elif request_type == 'analysis':
            category_chart = None
            reason_chart = None
            
            if result.get('success'):
                if result.get('category_chart_path'):
                    category_chart = get_chart_base64(result['category_chart_path'])
                    
                if result.get('reason_chart_path'):
                    reason_chart = get_chart_base64(result['reason_chart_path'])
            
            task_results[task_id] = {
                'status': 'completed',
                'success': result.get('success', False),
                'type': 'analysis',
                'result': result,
                'category_chart': category_chart,
                'reason_chart': reason_chart,
                'timestamp': datetime.now().isoformat()
            }
        else:
            task_results[task_id] = {
                'status': 'completed',
                'success': False,
                'type': 'error',
                'response': result.get('error', 'Bilinmeyen istek tipi'),
                'timestamp': datetime.now().isoformat()
            }
        
    except Exception as e:
        task_results[task_id] = {
            'status': 'error',
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }

# LLM işlemleri root_agent'da yapılıyor

@app.route('/')
def index():
    """Ana sayfa"""
    return render_template('index.html')

@app.route('/api/analyze', methods=['POST'])
def analyze():
    """Analiz isteği işleme"""
    global current_task, task_results
    
    try:
        data = request.get_json()
        prompt = data.get('prompt', '').strip()
        
        if not prompt:
            return jsonify({'success': False, 'error': 'Lütfen bir mesaj girin'})
        
        task_id = f"task_{int(time.time())}"
        current_task = task_id
        
        task_results[task_id] = {
            'status': 'processing',
            'prompt': prompt,
            'timestamp': datetime.now().isoformat()
        }
        
        thread = threading.Thread(target=process_request_async, args=(prompt, task_id))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'message': 'İşleniyor...'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/status/<task_id>')
def get_status(task_id):
    """Task durumunu al"""
    global task_results
    
    if task_id not in task_results:
        return jsonify({'success': False, 'error': 'Task bulunamadı'})
    
    result = task_results[task_id]
    
    response = {
        'success': True,
        'status': result['status'],
        'timestamp': result['timestamp']
    }
    
    if result['status'] == 'completed':
        if result['success']:
            if result.get('type') == 'chat':
                response.update({
                    'result': {
                        'success': True,
                        'type': 'chat',
                        'message': result.get('response', 'Yanıt alınamadı')
                    }
                })
            
            elif result.get('type') == 'analysis':
                analysis_result = result['result']
                
                data_info = {}
                if 'data_result' in analysis_result:
                    data_result = analysis_result['data_result']
                    data_info = {
                        'total_found': data_result.get('total_found', 0),
                        'uncategorized_count': data_result.get('uncategorized_count', 0)
                    }
                
                response.update({
                    'result': {
                        'success': True,
                        'type': 'analysis',
                        'data_info': data_info,
                        'category_chart': result.get('category_chart'),
                        'reason_chart': result.get('reason_chart')
                    }
                })
            
            else:
                response.update({
                    'result': {
                        'success': True,
                        'type': 'unknown',
                        'message': 'İstek işlendi ancak tip belirlenemedi'
                    }
                })
        else:
            response.update({
                'result': {
                    'success': False,
                    'error': result['result'].get('error', 'Bilinmeyen hata') if 'result' in result else result.get('error', 'Bilinmeyen hata')
                }
            })
    
    elif result['status'] == 'error':
        response.update({
            'result': {
                'success': False,
                'error': result.get('error', 'Bilinmeyen hata')
            }
        })
    
    return jsonify(response)

@app.route('/api/charts')
def get_charts():
    """Mevcut chart'ları al"""
    try:
        category_chart = get_chart_base64('category_chart.png')
        reason_chart = get_chart_base64('reason_chart.png')
        
        return jsonify({
            'success': True,
            'category_chart': category_chart,
            'reason_chart': reason_chart,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    if initialize_system():
        app.run(debug=False, host='0.0.0.0', port=5001)
