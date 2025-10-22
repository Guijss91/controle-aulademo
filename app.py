from flask import Flask, render_template, request, jsonify
from datetime import datetime, timedelta
import requests
import re

app = Flask(__name__)

# Lista de professores
PROFESSORES = ['Bruna', 'Caio', 'Weverton', 'Guilherme', 'Rodrigo', 'Sarah', 'Yago', 'Laura']

# URL do webhook n8n
N8N_WEBHOOK_URL = 'https://laboratorio-n8n.nu7ixt.easypanel.host/webhook/aula-demo'

@app.route('/')
def index():
    return render_template('index.html', professores=PROFESSORES)

@app.route('/agendar', methods=['POST'])
def agendar():
    try:
        data = request.get_json()
        
        # Validações
        if not data.get('professor'):
            return jsonify({'erro': 'Professor não selecionado'}), 400
        
        if not data.get('data_lembrete') or not data.get('hora_lembrete'):
            return jsonify({'erro': 'Data e hora do lembrete são obrigatórias'}), 400
        
        if not data.get('data_aula') or not data.get('hora_aula'):
            return jsonify({'erro': 'Data e hora da aula são obrigatórias'}), 400
        
        # Formatar datetime para Google Calendar API (ISO 8601)
        data_lembrete_str = data.get('data_lembrete')
        hora_lembrete_str = data.get('hora_lembrete')
        datetime_lembrete = datetime.strptime(f"{data_lembrete_str} {hora_lembrete_str}", "%Y-%m-%d %H:%M")
        datetime_lembrete_iso = datetime_lembrete.strftime("%Y-%m-%dT%H:%M:%S.000-03:00")
        
        # Calcular datetime_lembrete_plusone (1 hora a mais)
        datetime_lembrete_plusone = datetime_lembrete + timedelta(hours=1)
        datetime_lembrete_plusone_iso = datetime_lembrete_plusone.strftime("%Y-%m-%dT%H:%M:%S.000-03:00")
        
        # Formatar data e hora da aula (formato brasileiro)
        data_aula_str = data.get('data_aula')
        hora_aula_str = data.get('hora_aula')
        datetime_aula = datetime.strptime(f"{data_aula_str} {hora_aula_str}", "%Y-%m-%d %H:%M")
        datetime_aula_formatado = datetime_aula.strftime("%d/%m/%Y às %H:%M")
        
        # Nome do aluno (opcional)
        nome_aluno = data.get('nome_aluno', '').strip() if data.get('nome_aluno') else None
        
        # Processar telefone do aluno se fornecido
        telefone_aluno = None
        notificar_aluno = data.get('notificar_aluno', False)
        
        if notificar_aluno:
            ddd = data.get('ddd', '').strip()
            numero = data.get('numero', '').strip()
            
            if not ddd or not numero:
                return jsonify({'erro': 'DDD e número são obrigatórios quando notificar aluno está marcado'}), 400
            
            # Validar DDD (2 dígitos)
            if not re.match(r'^\d{2}$', ddd):
                return jsonify({'erro': 'DDD deve conter exatamente 2 dígitos'}), 400
            
            # Validar número (8 dígitos)
            if not re.match(r'^\d{8}$', numero):
                return jsonify({'erro': 'Número deve conter exatamente 8 dígitos (sem o 9 inicial)'}), 400
            
            telefone_aluno = f"55{ddd}{numero}"
        
        # Montar JSON para envio ao backend
        payload = {
            'professor': data.get('professor'),
            'datetime_lembrete': datetime_lembrete_iso,
            'datetime_lembrete_plusone': datetime_lembrete_plusone_iso,
            'datetime_aula': datetime_aula_formatado,
            'nome_aluno': nome_aluno,
            'notificar_professor': data.get('notificar_professor', True),
            'notificar_aluno': notificar_aluno,
            'telefone_aluno': telefone_aluno
        }
        
        # Enviar para o n8n
        try:
            response = requests.post(N8N_WEBHOOK_URL, json=payload, timeout=30)
            
            # Capturar a resposta de texto do n8n
            response_text = response.text.strip() if response.text else None
            
            # Verificar se a resposta foi bem-sucedida (2xx)
            if response.status_code >= 200 and response.status_code < 300:
                return jsonify({
                    'sucesso': True,
                    'mensagem': response_text if response_text else 'Lembrete agendado com sucesso!',
                    'dados': payload,
                    'status_code': response.status_code
                }), 200
            else:
                # Erro retornado pelo n8n
                return jsonify({
                    'sucesso': False,
                    'erro': response_text if response_text else f'Erro ao processar no n8n (Status: {response.status_code})',
                    'dados_enviados': payload,
                    'status_code': response.status_code
                }), response.status_code
            
        except requests.exceptions.Timeout:
            return jsonify({
                'erro': 'Timeout: O servidor n8n demorou muito para responder (mais de 30 segundos)',
                'dados_tentados': payload
            }), 504
        except requests.exceptions.ConnectionError:
            return jsonify({
                'erro': 'Erro de conexão: Não foi possível conectar ao servidor n8n',
                'dados_tentados': payload
            }), 503
        except requests.exceptions.RequestException as e:
            return jsonify({
                'erro': f'Erro ao enviar para o n8n: {str(e)}',
                'dados_tentados': payload
            }), 500
        
    except ValueError as e:
        return jsonify({'erro': f'Erro ao processar data/hora: {str(e)}'}), 400
    except Exception as e:
        return jsonify({'erro': f'Erro interno: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
