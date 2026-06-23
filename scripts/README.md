# Deployment systemd de Manejadora App

Esta carpeta instala la aplicación Python de este repositorio como un servicio `systemd` único llamado `manejadora_app.service`. El monitor web ya forma parte de `main.py`, así que no hay una unidad separada para UI.

## Componentes

- `install.sh`: instala o actualiza las unidades systemd.
- `uninstall.sh`: remueve las unidades systemd y, opcionalmente, el directorio de variables de entorno.
- `manejadora_app.service.in`: plantilla de la unidad principal.
- `manejadora_app.target`: target opcional para operar el stack como grupo.
- `manejadora_app.env.example`: ejemplo de variables de entorno para auth y branding del monitor.
- `../requirements.txt`: dependencias congeladas a partir del `my_venv` funcional del repo.

## Estructura esperada

El instalador asume esta estructura:

```text
manejadora_app/
  main.py
  requirements.txt
  my_venv/
  logs/
  var/
  scripts/
```

Por default:

- `APP_ROOT` se detecta como la carpeta padre de `scripts/`.
- `PYTHON_BIN` apunta a `APP_ROOT/my_venv/bin/python3.12`.
- Si ese binario no existe, el instalador intenta `APP_ROOT/my_venv/bin/python`.

## Prerrequisitos

```bash
cd /ruta/manejadora_app
python3.12 -m venv my_venv
date
sudo timedatectl set-ntp true
sudo systemctl restart systemd-timesyncd
timedatectl

./my_venv/bin/python -m pip install --upgrade pip
./my_venv/bin/python -m pip install -r requirements.txt
chmod +x scripts/install.sh scripts/uninstall.sh
sudo usermod -aG dialout dynatek
sudo chown -R dynatek:dynatek /home/dynatek/manejadora_app/logs && sudo chmod 775 /home/dynatek/manejadora_app/logs
```

```bash
sudo sh -c 'cat > /etc/resolv.conf << EOF
nameserver 8.8.8.8
nameserver 1.1.1.1
EOF'
```


El servicio necesita permisos de lectura y escritura sobre `logs/` y `var/`, además de acceso al puerto Modbus configurado en `var/const.py` cuando `use_modbus_hw = True`.

## Instalación

```bash
cd /ruta/manejadora_app/scripts
sudo ./install.sh
```

Variables soportadas por el instalador:

- `APP_ROOT`: raíz del proyecto. Default: carpeta padre de `scripts/`.
- `PYTHON_BIN`: intérprete Python a usar. Default: `APP_ROOT/my_venv/bin/python3.12`.
- `SERVICE_USER`: usuario que ejecutará el servicio. Default: usuario que invocó `sudo`.
- `SERVICE_GROUP`: grupo primario de `SERVICE_USER`.
- `SYSTEMD_DIR`: destino de unidades. Default: `/etc/systemd/system`.
- `ENV_DIR`: destino del archivo de entorno. Default: `/etc/manejadora_app`.

Ejemplo explícito:

```bash
cd /ruta/manejadora_app/scripts
sudo APP_ROOT=/opt/manejadora_app \
  PYTHON_BIN=/opt/manejadora_app/my_venv/bin/python3.12 \
  SERVICE_USER=dynatek \
  ./install.sh
```

## Configuración runtime del servicio

El instalador crea `/etc/manejadora_app/manejadora_app.env` a partir de `manejadora_app.env.example` si todavía no existe. Ese archivo sirve para cambiar credenciales o branding del monitor sin tocar el código:

```bash
sudo nano /etc/manejadora_app/manejadora_app.env
sudo systemctl restart manejadora_app.service
```

La configuración operativa del controlador sigue viviendo en:

- `var/const.py`
- `var/runtime_config.json`

## Operación diaria

```bash
sudo systemctl start manejadora_app.service
sudo systemctl stop manejadora_app.service
sudo systemctl restart manejadora_app.service
sudo systemctl status manejadora_app.service
sudo systemctl start manejadora_app.target
sudo systemctl stop manejadora_app.target
```

Logs:

```bash
journalctl -u manejadora_app.service -f
```

Verificación de unidad instalada:

```bash
sudo systemd-analyze verify /etc/systemd/system/manejadora_app.service
```

## Monitor HTTP

El monitor queda disponible en el host y puerto configurados por `var/const.py`, por default `0.0.0.0:8088`.

Endpoints útiles:

- `GET /`: interfaz web integrada.
- `GET /api/status`: estado del controlador.
- `GET /api/runtime`: configuración editable en caliente.
- `POST /api/runtime`: aplica configuración permitida.
- `GET /api/force`: sensores forzados activos para simulación.
- `POST /api/force`: reemplaza sensores forzados.
- `POST /api/force/clear`: limpia sensores forzados.

El archivo de entorno puede sobrescribir:

- `MONITOR_AUTH_USER`
- `MONITOR_AUTH_PASSWORD`
- `MONITOR_UNIT_NAME`
- `MONITOR_TAGLINE`
- `MONITOR_LOGO_PATH`

## Desinstalación

```bash
cd /ruta/manejadora_app/scripts
sudo ./uninstall.sh
```

Para borrar también `/etc/manejadora_app`:

```bash
cd /ruta/manejadora_app/scripts
sudo REMOVE_ENV=true ./uninstall.sh
```
