"""
Módulo independiente para visualizaciones con displaCy y guardado en disco.
Contiene funciones para renderizar (ent/dep), servir (opcional) y guardar HTML/SVG en
la carpeta archivos_spacy del proyecto.

CONFIGURACIÓN GLOBAL (modificar aquí para activar/desactivar visualización):
"""
from typing import Optional, Dict, Any
import os
import base64
from datetime import datetime
import uuid
import spacy
from spacy import displacy


# ========== CONFIGURACIÓN CENTRAL DE VISUALIZACIÓN ==========
# Modificar estas variables para activar/desactivar visualización en TODO el sistema
VISUALIZACION_HABILITADA = False  # True: genera visualización, False: no genera nada
GUARDADO_HABILITADO = False       # True: guarda en disco, False: solo genera en memoria
ESTILO_POR_DEFECTO = "ent"        # 'ent' o 'dep'
OPCIONES_POR_DEFECTO = {          # Opciones de displaCy (colores, compact, etc.)
    "compact": False,
    "colors": {
        "PER": "#f39c12",
        "ORG": "#3498db",
        "LOC": "#2ecc71",
        "MISC": "#9b59b6"
    }
}
# =============================================================


def _default_save_dir() -> str:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
    return os.path.join(repo_root, 'archivos_spacy')


def is_visualization_enabled() -> bool:
    """Retorna si la visualización está habilitada globalmente."""
    return VISUALIZACION_HABILITADA


def is_save_enabled() -> bool:
    """Retorna si el guardado está habilitado globalmente."""
    return GUARDADO_HABILITADO


def render_visualization(doc, style: str = 'ent', options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Renderiza con displaCy y devuelve un diccionario con el HTML/SVG en la clave 'content'."""
    result: Dict[str, Any] = {'style': style}
    try:
        content = displacy.render(doc, style=style, options=options or {})
        result['content'] = content
    except Exception as e:
        result['error'] = str(e)
    return result


def serve_visualization(doc, style: str = 'ent', options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Arranca displacy.serve (bloqueante). Útil solo para desarrollo local.
    Retorna metadatos si la llamada tuvo éxito.
    """
    result: Dict[str, Any] = {'style': style}
    try:
        displacy.serve(doc, style=style, options=options or {})
        result['served'] = True
    except Exception as e:
        result['error'] = str(e)
    return result


def save_visualization_content(content: str, style: str = 'ent', save_dir: Optional[str] = None) -> Dict[str, Any]:
    """Guarda content (HTML o SVG) en disco. Devuelve info del archivo guardado.
    Si style == 'dep' guardamos como .svg, en otro caso como .html.
    """
    if save_dir is None:
        save_dir = _default_save_dir()
    os.makedirs(save_dir, exist_ok=True)

    timestamp = datetime.utcnow().strftime('%Y%m%dT%H%M%S')
    unique = uuid.uuid4().hex[:8]
    ext = 'svg' if style == 'dep' else 'html'
    filename = f'displacy_{style}_{timestamp}_{unique}.{ext}'
    path = os.path.join(save_dir, filename)

    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(content)

    result: Dict[str, Any] = {
        'path': path,
        'filename': filename,
        'url_file': f'file://{path}'
    }

    if ext == 'svg':
        result['svg_base64'] = base64.b64encode(content.encode('utf-8')).decode('utf-8')

    return result


def render_and_maybe_save(doc, style: Optional[str] = None, options: Optional[Dict[str, Any]] = None, serve: bool = False, save: Optional[bool] = None, save_dir: Optional[str] = None) -> Dict[str, Any]:
    """Función de conveniencia que renderiza (o sirve) y opcionalmente guarda el resultado.
    Usa la CONFIGURACIÓN GLOBAL del módulo si no se especifican parámetros.
    
    Para activar/desactivar visualización en TODO el sistema, cambiar las constantes
    VISUALIZACION_HABILITADA y GUARDADO_HABILITADO al inicio de este módulo.
    
    Retorna un dict con claves: content (si generó), error, served, saved (info de archivo).
    Si la visualización está deshabilitada globalmente, retorna dict con 'disabled': True.
    """
    # Verificar si la visualización está habilitada globalmente
    if not VISUALIZACION_HABILITADA:
        return {
            'disabled': True,
            'note': 'Visualization is globally disabled. Set VISUALIZACION_HABILITADA=True in visualization_displacy.py to enable.'
        }
    
    # Usar valores por defecto si no se especifican
    if style is None:
        style = ESTILO_POR_DEFECTO
    if options is None:
        options = OPCIONES_POR_DEFECTO
    if save is None:
        save = GUARDADO_HABILITADO
    
    out: Dict[str, Any] = {'style': style}
    
    if serve:
        out.update(serve_visualization(doc, style=style, options=options))
        return out

    render_res = render_visualization(doc, style=style, options=options)
    out.update(render_res)

    if save and 'content' in render_res and render_res.get('error') is None:
        saved = save_visualization_content(render_res['content'], style=style, save_dir=save_dir)
        out['saved'] = saved

    return out
