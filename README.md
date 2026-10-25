# Arriendos Gran Concepción

Estudio de precios de arriendo de casas y departamentos en el Gran Concepción,
a partir de avisos publicados en Portal Inmobiliario (Mercado Libre).

## Estructura

```
arriendo-gran-concepcion/
├── notebooks/
│   └── 01_portal.ipynb      # descarga, calidad, procesamiento y mapa
├── src/
│   ├── config.py            # comunas, tipos de propiedad y URL base
│   ├── geocoding.py         # dirección -> lat/lon (Nominatim, con caché)
│   └── portal/
│       ├── scraper.py       # extrae los datos del HTML de una página
│       └── crawler.py       # recorre páginas y guarda un CSV por búsqueda
├── data/                    # no se sube a GitHub
│   ├── raw/portal/<fecha>/  # un CSV por comuna y tipo
│   └── processed/           # CSV final + caché de coordenadas
└── requirements.txt
```

## 0. Instalación

Requiere Python 3.10 o superior.

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium          # el navegador no se instala con pip

# Registrar el entorno como kernel de Jupyter
python -m ipykernel install --user --name arriendos --display-name "Python (arriendos)"
```

En VS Code, elegir el kernel `.venv` (o "Python (arriendos)") arriba a la derecha
del notebook. Para verificar: `import sys; sys.executable` debe terminar en `.venv/bin/python`.

## 1. Ejecución

Abrir `notebooks/01_portal.ipynb` y ejecutar **Run All**. Secciones:

| Sección | Qué hace | Tiempo aprox. |
|---|---|---|
| 1. Setup | Imports y rutas | — |
| 2. Descarga | Recorre todas las comunas y tipos y guarda `data/raw/portal/<fecha>/` | 10–15 min |
| 3. Carga | Une los CSV de la última corrida | — |
| 4. Calidad | Columnas con valores vacíos | — |
| 5. Procesamiento | Quita duplicados, filtra, agrega coordenadas y guarda `data/processed/portal_<fecha>.csv` | 20–40 min la primera vez |
| 6. Mapa | Mapa de verificación de los puntos | — |

- Para una **prueba rápida**, en la sección 2 usar 2 comunas y `MAX_PAGES = 3`.
- Para **analizar sin descargar**, saltarse la sección 2.
- Si la descarga se interrumpe, volver a ejecutarla: las búsquedas ya guardadas
  ese día se saltan.
- La geolocalización guarda un caché (`data/processed/geocode_cache.csv`):
  cada dirección se consulta una sola vez, así que las corridas siguientes tardan segundos.

También se puede descargar desde la terminal (desde la raíz del proyecto):

```bash
python -m src.portal.crawler
```

## 2. Datos generados

`data/processed/portal_<fecha>.csv`, un aviso por fila:

| Columna | Descripción |
|---|---|
| `source` | Sitio de origen |
| `id` | Código del aviso (`MLC...`) |
| `commune` | Comuna de la búsqueda |
| `property_type` | `departamento` o `casa` |
| `title` | Título del aviso |
| `price`, `currency` | Precio publicado y moneda (`CLP` o `UF`) |
| `bedrooms`, `bathrooms` | Dormitorios y baños |
| `usable_m2` | Metros cuadrados útiles |
| `location`, `neighborhood` | Dirección y barrio |
| `url` | Enlace al aviso |
| `scraped_at` | Fecha de descarga |
| `lat`, `lon` | Coordenadas |
| `precision` | `address`, `street`, `neighborhood` o `not_found` |

## 3. Limitaciones

- Son **precios publicados**, no precios de arriendo cerrados.
- Es una foto de un día: los avisos que llevan mucho tiempo publicados
  (a menudo los más caros) tienen más peso que los que se arriendan rápido.
- Algunos avisos vienen en UF; hay que convertirlos a pesos para comparar.
- Lota, Penco, Hualqui y Tomé tienen muy pocos avisos (o ninguno) en Portal Inmobiliario,
  así que sus precios deben leerse con cautela.
- La precisión de las coordenadas depende de la dirección publicada: muchos avisos
  no traen número de calle.

## 4. Uso responsable

- El crawler hace pausas aleatorias de 2 a 5 segundos entre páginas y usa un solo navegador.
- La geolocalización usa Nominatim (OpenStreetMap) a 1 consulta por segundo,
  según su política de uso.
- Los datos descargados no se publican en el repositorio (`data/` está en `.gitignore`).