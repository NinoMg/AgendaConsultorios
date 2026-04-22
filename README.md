# 🏥 Agenda de Turnos — Consultorios

App web para gestión de turnos médicos. Construida con Flask + PostgreSQL.

## Estructura

```
AgendaConsultorios/
├── app.py                  # Lógica principal
├── requirements.txt
├── Procfile                # Para Render
├── static/
│   └── style.css           # Todos los estilos
└── templates/
    ├── index.html          # Página del paciente
    ├── login.html          # Login del médico
    └── panel.html          # Panel de gestión
```

## Variables de entorno (configurar en Render)

| Variable | Descripción | Ejemplo |
|---|---|---|
| `DATABASE_URL` | URL de PostgreSQL | `postgresql://...` |
| `SECRET_KEY` | Clave secreta Flask | cualquier string largo |
| `MEDICO_USUARIO` | Usuario del panel | `dr_garcia` |
| `MEDICO_PASSWORD` | Contraseña del panel | `MiClave2024` |
| `MEDICO_WHATSAPP` | Número WhatsApp del médico | `5492604123456` |
| `NOMBRE_CONSULTORIO` | Nombre que aparece en la app | `Dr. García - Neurología` |

## Deploy en Render

1. Subir el proyecto a GitHub
2. Crear nuevo Web Service en Render conectado al repo
3. Configurar las variables de entorno arriba
4. Crear una base de datos PostgreSQL en Render y copiar la DATABASE_URL
5. ¡Listo!

## Funcionalidades

- ✅ Pacientes reservan turno online (nombre, fecha, hora, obra social, motivo)
- ✅ Confirmación automática por WhatsApp
- ✅ Login seguro para el médico
- ✅ Panel para ver todos los turnos
- ✅ Cancelar turno (con opción de notificar al paciente por WhatsApp)
- ✅ Eliminar turno permanentemente
- ✅ Bloqueo de horarios duplicados
- ✅ Fechas pasadas bloqueadas en el formulario
