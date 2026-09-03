# Llevar fontana_movimientos a un servidor separado de la base de datos

Arquitectura objetivo: la base de datos MySQL sigue en la máquina
`192.168.2.105` (sin cambios ahí más que habilitar el acceso remoto si
hiciera falta), el proyecto Django corre en una máquina Windows distinta
("el servidor de la app"), y el resto de las PCs de la red entran por
navegador a `http://<IP-del-servidor-de-la-app>:8000/`.

Falta un dato para dejar todo esto ya armado: **la IP (o nombre) de la
máquina nueva** donde va a correr Django. En cuanto me la pases, te ajusto
`settings/prod.py` y el `.env` con el valor correcto — mientras tanto, esta
guía usa `<IP_SERVIDOR_APP>` como placeholder para que puedas ir
completando vos.

## 0. Antes de arrancar: qué es cada cosa en el proyecto

Reviasndo el proyecto vi que ya está preparado para esto, con un par de
cosas para ajustar:

- `settings/dev.py` y `settings/prod.py` ya leen los datos de conexión a
  MySQL desde variables de entorno (el archivo `.env`), así que no hace
  falta tocar código para apuntar a la base — solo el `.env`.
- El `.env` actual ya tiene `DB_HOST=192.168.2.105`, así que **no hay que
  cambiar nada ahí para la conexión a la base**, solo copiarlo tal cual a
  la máquina nueva.
- `settings/prod.py` tiene un `ALLOWED_HOSTS` **hardcodeado** con una IP
  vieja (`192.168.2.185`) que ya no corresponde — hay que reemplazarla por
  la IP real de la máquina nueva (ver sección 2.4).
- El `.env` tiene `DJANGO_SECRET_KEY=your_secret_key`, un valor de
  ejemplo, no una clave real. Para un sistema que va a usar toda la
  empresa por red conviene generar una de verdad (paso 2.4).
- No hay un `requirements.txt` en el proyecto todavía, así que instalar
  las dependencias en la máquina nueva a ciegas no es seguro — lo
  generamos desde tu entorno actual (paso 2.2).

## 1. Base de datos (192.168.2.105): verificar acceso remoto

Como tu PC actual ya se conecta a esa base estando en otra máquina, es
probable que el acceso remoto ya esté habilitado en general. Aun así,
conviene verificar estos tres puntos ahí (en la máquina `192.168.2.105`),
porque a veces el acceso remoto está permitido solo para IPs puntuales:

**1.1. MySQL escucha en la red, no solo en localhost.**
Abrí el archivo de configuración de MySQL (normalmente
`C:\ProgramData\MySQL\MySQL Server 8.0\my.ini`) y confirmá que la línea
`bind-address` sea `0.0.0.0` (todas las interfaces) o directamente no
esté presente (que también significa "todas"). Si dice `127.0.0.1`, hay
que cambiarla a `0.0.0.0` y reiniciar el servicio de MySQL (Servicios de
Windows → MySQL80 → Reiniciar).

**1.2. El usuario de la base acepta conexiones desde la máquina nueva.**
Con un cliente MySQL (Workbench, o `mysql -u root -p` desde esa misma
máquina), revisá qué hosts tiene autorizado el usuario `Gaston`:

```sql
SELECT user, host FROM mysql.user WHERE user = 'Gaston';
```

Si ves `'Gaston'@'%'` (el símbolo `%` = cualquier host), ya está listo. Si
en cambio ves hosts puntuales y no incluye a la máquina nueva, agregale
permiso:

```sql
CREATE USER IF NOT EXISTS 'Gaston'@'%' IDENTIFIED BY 'Juli2024E';
GRANT ALL PRIVILEGES ON fontana.* TO 'Gaston'@'%';
FLUSH PRIVILEGES;
```

(Se puede restringir a la IP puntual de la máquina nueva en vez de `%`,
por ejemplo `'Gaston'@'192.168.2.XXX'`, si preferís no dejarlo abierto a
toda la red — más seguro, pero hay que repetir el `GRANT` si esa IP
cambia.)

**1.3. El firewall de esa máquina deja pasar el puerto 3306.**
En "Firewall de Windows Defender con seguridad avanzada" → Reglas de
entrada → Nueva regla → Puerto → TCP 3306 → Permitir la conexión. Si ya
existe una regla para MySQL, no hace falta duplicarla.

**Para probar que quedó bien**, desde la máquina nueva (una vez que tenga
Python instalado, sección 2.1) podés correr:

```
mysql -h 192.168.2.105 -u Gaston -p fontana
```

Si conecta y te deja hacer `SHOW TABLES;`, esta parte está lista.

## 2. Servidor de la app (la máquina nueva, Windows)

**2.1. Instalar Python.**
Descargá e instalá la misma versión mayor que usás en tu PC de desarrollo
(Python 3.11 o 3.12) desde python.org. Durante la instalación, marcá la
casilla "Add python.exe to PATH".

**2.2. Copiar el proyecto y generar `requirements.txt`.**
Como el proyecto todavía no tiene un `requirements.txt`, generalo antes
desde tu entorno de desarrollo actual (la PC donde ya funciona), para
llevarte exactamente lo que hace falta:

```
cd "C:\Users\Gaston C\fontana_movimientos"
pip freeze > requirements.txt
```

Revisá que aparezcan al menos `Django`, `django-environ`,
`django-select2` y el conector de MySQL (`mysqlclient` o `PyMySQL`, según
cuál hayas instalado). Copiá la carpeta completa del proyecto (ya con este
`requirements.txt` adentro) a la máquina nueva, por ejemplo a
`C:\fontana_movimientos` — por red, USB o como te resulte más cómodo. No
hace falta llevar la carpeta `backups` ni los `.sql` sueltos si pesan
mucho, no los usa la aplicación para correr.

**2.3. Crear el entorno virtual e instalar dependencias.**
Ya en la máquina nueva, en una consola dentro de la carpeta del proyecto:

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

**2.4. Ajustar la configuración para esta máquina.**
Editá el `.env` (ya viene copiado con los datos de la base, no hace falta
tocar esa parte) y cambiá estas dos líneas:

```
DEBUG=False
DJANGO_ALLOWED_HOSTS=<IP_SERVIDOR_APP>,127.0.0.1,localhost
```

Y generá una `SECRET_KEY` real para reemplazar el valor de ejemplo:

```
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Pegá el resultado en el `.env`:

```
DJANGO_SECRET_KEY=<lo que te haya generado el comando de arriba>
```

Después, en `settings\prod.py`, reemplazá la lista `ALLOWED_HOSTS`
hardcodeada por la IP real de esta máquina (o dejá que tome la del
`.env`, ver nota abajo):

```python
ALLOWED_HOSTS = [
    'localhost',
    '127.0.0.1',
    '<IP_SERVIDOR_APP>',
]
```

*(Nota técnica: hoy `prod.py` pisa el `ALLOWED_HOSTS` que ya arma
`base.py` a partir del `.env`, así que cambiar el `.env` solo no alcanza
mientras se use `settings.prod` — hay que tocar esta lista también, o
avisame y te dejo `prod.py` tomando el valor del `.env` directamente para
no tener que editar código en cada máquina donde se instale.)*

**2.5. Usar la configuración de producción.**
El proyecto trae `settings/dev.py` (`DEBUG=True`, pensado para tu PC de
desarrollo) y `settings/prod.py` (`DEBUG=False`, para esto). En vez de
editar `manage.py`, seleccioná `prod` con una variable de entorno al
arrancar — así el mismo código sirve en ambas máquinas sin tocarlo:

```
set DJANGO_SETTINGS_MODULE=settings.prod
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
```

(`migrate` no debería crear tablas nuevas, ya existen en la base — pero
conviene correrlo igual para que Django registre qué migraciones están
aplicadas. `collectstatic` junta los archivos estáticos en un solo lugar
para servirlos en producción.)

**2.6. Probar antes de dejarlo automático.**
Con el entorno virtual activado y `DJANGO_SETTINGS_MODULE` seteado como
arriba:

```
python manage.py runserver 0.0.0.0:8000
```

Desde otra PC de la red, abrí `http://<IP_SERVIDOR_APP>:8000/` en el
navegador. Si carga, la conexión a la base y la configuración están bien.
Frená el servidor (Ctrl+C) antes de seguir — `runserver` es solo para
probar, no para dejarlo corriendo de verdad (no está pensado para uso
real ni para varias personas a la vez).

## 3. Dejarlo corriendo siempre, sin depender de una consola abierta

Para producción se usa un servidor de aplicaciones en vez de `runserver`.
En Windows, el más simple es **waitress**:

```
pip install waitress
```

Guardá este archivo como `iniciar_servidor.py` en la raíz del proyecto:

```python
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings.prod')

from waitress import serve
from fontana_movimientos.wsgi import application

if __name__ == '__main__':
    serve(application, host='0.0.0.0', port=8000, threads=8)
```

Probalo a mano primero: `venv\Scripts\python.exe iniciar_servidor.py` y
entrá de nuevo desde otra PC a `http://<IP_SERVIDOR_APP>:8000/`.

**Para que arranque solo con la máquina** (sin necesitar que alguien
inicie sesión), usá el Programador de tareas de Windows:

1. Abrir "Programador de tareas" → "Crear tarea..." (no "tarea básica",
   para tener la opción de "ejecutar independientemente de que el usuario
   haya iniciado sesión").
2. Pestaña General: nombre "fontana_movimientos", marcar "Ejecutar tanto
   si el usuario inició sesión como si no" y "Ejecutar con los máximos
   privilegios".
3. Pestaña Desencadenadores: Nuevo → "Al iniciar el sistema".
4. Pestaña Acciones: Nueva → Programa/script:
   `C:\fontana_movimientos\venv\Scripts\python.exe`, argumentos:
   `iniciar_servidor.py`, "Iniciar en":
   `C:\fontana_movimientos`.
5. Pestaña Configuración: marcar "Si la tarea produce un error,
   reiniciarla cada" 1 minuto, un número de reintentos alto (por ejemplo
   999), para que si el proceso se cae por lo que sea, se levante solo.

Con esto, cada vez que se prenda o reinicie esa máquina, el sistema queda
disponible en la red sin que nadie tenga que abrir nada a mano.

## 4. Firewall de la máquina nueva

Igual que con el puerto 3306 en la base, hay que abrir el puerto 8000 acá:
Firewall de Windows Defender → Reglas de entrada → Nueva regla → Puerto →
TCP 8000 → Permitir la conexión (podés restringirlo al rango de IPs de tu
red local si querés ser más estricto).

## 5. Uso desde las demás PCs

Cualquier PC de la misma red entra con un navegador a:

```
http://<IP_SERVIDOR_APP>:8000/
```

Conviene que esa máquina tenga **IP fija** (reservada en el router, o
configurada a mano), para que la dirección no cambie con el tiempo y
tengas que volver a avisarle a todos.

## 6. Pendientes / a confirmar

- Pasame la IP real de la máquina nueva para dejarte `prod.py` y el
  `.env` ya completos, en vez de con el placeholder.
- Confirmame la versión de MySQL y si usás `mysqlclient` o `PyMySQL` como
  conector, así el `requirements.txt` queda bien de entrada.
- Este documento asume que las dos máquinas están en la misma red local
  (mismo rango 192.168.2.x) y que nadie va a acceder desde afuera de la
  oficina; si en algún momento hiciera falta acceso remoto (por ejemplo
  desde tu casa), eso es un paso aparte (VPN o exponer el puerto con
  cuidado) que no cubre esta guía.
