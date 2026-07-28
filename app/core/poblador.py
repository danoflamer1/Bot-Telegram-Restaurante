from datetime import datetime
from app.core.database import SessionLocal, engine, Base
from app.models.modelos import Plato

Base.metadata.create_all(bind=engine)


def poblar_menu_ejemplo():
    db = SessionLocal()
    fecha_hoy = datetime.now().strftime("%Y-%m-%d")

    existentes = db.query(Plato).filter(Plato.fecha_menu == fecha_hoy).count()
    if existentes == 0:
        platos = [
            Plato(
                nombre="Sopa de Mani y Silpancho",
                descripcion="Plato completo tradicional",
                precio=20.0,
                stock=15,
                fecha_menu=fecha_hoy,
                disponible=True,
            ),
            Plato(
                nombre="Almuerzo Fricase",
                descripcion="Incluye refresco de mocochinchi",
                precio=25.0,
                stock=10,
                fecha_menu=fecha_hoy,
                disponible=True,
            ),
            Plato(
                nombre="Plato Vegetariano",
                descripcion="Ensalada fresca y tortilla de verduras",
                precio=18.0,
                stock=5,
                fecha_menu=fecha_hoy,
                disponible=True,
            ),
        ]
        db.add_all(platos)
        db.commit()
        print(f"Se agregaron {len(platos)} platos de prueba para la fecha {fecha_hoy}")
    db.close()

if __name__ == "__main__":
    poblar_menu_ejemplo()