from app.bot.cliente import crear_aplicacion_bot

# El TOKEN DEBE ir entre comillas
TOKEN = "8721377188:AAEfXfkEQOkFSseR1nFpessfq94JTKhiIs4"

if __name__ == "__main__":
    print("Iniciando Bot de Telegram para pruebas...")
    app = crear_aplicacion_bot(TOKEN)
    app.run_polling()