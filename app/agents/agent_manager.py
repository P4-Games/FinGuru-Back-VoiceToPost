"""
Módulo para la gestión de agentes del sistema de tendencias automatizado.
Proporciona funcionalidades para obtener, inicializar y configurar agentes.
"""

import html
import requests
from typing import Dict, Any, List


class AgentManager:
    """Gestor de agentes para el sistema de tendencias automatizado"""
    
    def __init__(self, next_public_api_url: str, sudo_api_key: str):
        self.next_public_api_url = next_public_api_url
        self.sudo_api_key = sudo_api_key
    
    def get_available_agents(self) -> Dict[str, Any]:
        """Obtiene todos los agentes disponibles desde la API"""
        try:
            print("Obteniendo agentes disponibles desde la API...")
            
            endpoint = f"{self.next_public_api_url}/agent-ias?populate=*"
            
            headers = {
                "Authorization": f"Bearer {self.sudo_api_key}",
                "Content-Type": "application/json",
            }
            
            response = requests.get(endpoint, headers=headers)
            
            if not response.ok:
                raise Exception(f"HTTP error! status: {response.status_code}")
            
            data = response.json()
            
            if 'details' in data:
                agents = data['details']
            else:
                agents = data.get('data', [])
                if isinstance(agents, list) and agents:                    
                    processed_agents = []
                    for agent in agents:
                        if isinstance(agent, dict):
                            # Extraer userId del usuario poblado
                            user_id = None
                            user_data = agent.get('attributes', {}).get('user', {})
                            if isinstance(user_data, dict) and 'data' in user_data:
                                user_id = user_data.get('data', {}).get('id')
                            elif isinstance(user_data, dict) and 'id' in user_data:
                                user_id = user_data.get('id')
                            
                            processed_agent = {
                                'id': agent.get('id'),
                                'name': agent.get('attributes', {}).get('name', f"agent-{agent.get('id')}"),
                                'personality': agent.get('attributes', {}).get('personality', ''),
                                'trending': agent.get('attributes', {}).get('trending', ''),
                                'format_markdown': agent.get('attributes', {}).get('format_markdown', ''),
                                'userId': user_id,
                                'createdAt': agent.get('attributes', {}).get('createdAt', ''),
                                'updatedAt': agent.get('attributes', {}).get('updatedAt', ''),
                                'publishedAt': agent.get('attributes', {}).get('publishedAt', '')
                            }
                            processed_agents.append(processed_agent)
                    agents = processed_agents
            
            print(f"Se encontraron {len(agents)} agentes disponibles")
            for agent in agents:
                print(f"   - ID: {agent.get('id')}, Nombre: {agent.get('name')}")
            
            return {
                'status': 'success',
                'details': agents,
                'total': len(agents)
            }
            
        except Exception as e:
            print(f"Error obteniendo agentes desde la API: {str(e)}")
            return {
                'status': 'error',
                'message': str(e),
                'details': [],
                'total': 0
            }
    
    def initialize_agents(self, automated_trends_agent_class) -> List:
        """Inicializa todos los agentes disponibles con sus configuraciones únicas"""
        try:
            print("Inicializando agentes múltiples...")
            
            agents_response = self.get_available_agents()
            
            if agents_response.get('status') != 'success':
                print(f"Error obteniendo agentes: {agents_response.get('message')}")
                return []
            
            agents_data = agents_response.get('details', [])
            initialized_agents = []
            
            for agent_data in agents_data:
                try:
                    format_markdown = agent_data.get('format_markdown', '')
                    if format_markdown:
                        format_markdown = html.unescape(format_markdown)
                    
                    agent_id = agent_data.get('id')
                    agent_user_id = agent_data.get('userId')
                    
                    if not agent_user_id:
                        print(f"No se encontró userId para el agente {agent_id}, usando ID por defecto")
                        agent_user_id = 5822
                    
                    agent_config = {
                        'id': agent_id,
                        'name': agent_data.get('name'),
                        'personality': agent_data.get('personality', ''),
                        'trending': agent_data.get('trending', ''),
                        'format_markdown': format_markdown,
                        'userId': agent_user_id,
                        'createdAt': agent_data.get('createdAt'),
                        'updatedAt': agent_data.get('updatedAt')
                    }
                    
                    agent_instance = automated_trends_agent_class(agent_config)
                    initialized_agents.append(agent_instance)
                    
                    user_status = "real (bd)" if agent_data.get('userId') else "fallback"
                    print(f"Agente inicializado: ID {agent_config['id']} - {agent_config['name']} (UserId: {agent_user_id} - {user_status})")
                    
                except Exception as e:
                    print(f"Error inicializando agente {agent_data.get('id', 'unknown')}: {str(e)}")
                    continue
            
            print(f"Total de agentes inicializados: {len(initialized_agents)}")
            return initialized_agents
            
        except Exception as e:
            print(f"Error general inicializando agentes: {str(e)}")
            return []