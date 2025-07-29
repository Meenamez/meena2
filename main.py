import os
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler
)
from sqlalchemy import create_engine, Column, String, Integer, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker

# Load environment variables
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
DB_URL = os.getenv("DATABASE_URL")

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Database setup
Base = declarative_base()
engine = create_engine(DB_URL)
Session = sessionmaker(bind=engine)

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, unique=True)
    first_name = Column(String)
    last_name = Column(String)
    email = Column(String)
    key = Column(String)
    used = Column(Boolean, default=False)

class KeyPool(Base):
    __tablename__ = 'keys'
    id = Column(Integer, primary_key=True)
    key = Column(String, unique=True)
    used = Column(Boolean, default=False)

# Create tables
Base.metadata.create_all(engine)

# Predefined keys
KEYS = [
    "kL8!p@3Qz#mR9$W", "T5^fG7vY*2qPx!N", "#9Hj$B4nL6@kXpM", "s3$KpL!8mZ2@rF9",
    "Q@6dN9#vP4!xL7T", "2W!e8R$pY5#kL9M", "g7@Xm!3PqL9$zN4", "F5#tH9$kL2!pR7@",
    "n4!Lp@8mK3#zQ6T", "R7$kP9!xL2@mN5#", "M3@qL!9tP5#kX8$", "Z2!wL7$pN4@kR9#",
    "9L#kP5!mX3@tN7$", "p4$mL8!kQ3#zR9@", "T6#kX9$pL2!mN7@", "B3@mN7!kL4#pQ9$",
    "K5!tL9$pR2@mN7#", "L8#kP3!mX6$qN9@", "N2$mL7!kQ4#pR9@", "X5!kL9$pM3@tN7#",
    "P4@mN7!kL2#qR9$", "Q3!tL8$pK6#mN9@", "R7#kP9!mL4$zN2@", "S5$mL8!kN3@pQ9#",
    "W2!kL7$pN4#mR9@"
]

# Initialize key pool
def init_keys():
    session = Session()
    try:
        if session.query(KeyPool).count() == 0:
            for key in KEYS:
                session.add(KeyPool(key=key))
            session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Key init error: {e}")
    finally:
        session.close()

# Conversation states
FIRST_NAME, LAST_NAME, EMAIL = range(3)

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    session = Session()
    
    # Check if user already claimed
    if session.query(User).filter_by(user_id=user_id).first():
        await update.message.reply_text("You've already claimed your key!")
        session.close()
        return ConversationHandler.END
    
    session.close()
    await update.message.reply_text("Welcome to Token Airdrop!\nPlease enter your first name:")
    return FIRST_NAME

# Cancel handler
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Operation cancelled.")
    return ConversationHandler.END

# Handle first name
async def get_first_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['first_name'] = update.message.text
    await update.message.reply_text("Now enter your last name:")
    return LAST_NAME

# Handle last name
async def get_last_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['last_name'] = update.message.text
    await update.message.reply_text("Finally, enter your email address:")
    return EMAIL

# Handle email and assign key
async def get_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    email = update.message.text
    user_id = update.effective_user.id
    session = Session()
    
    # Validate email format
    if "@" not in email or "." not in email:
        await update.message.reply_text("Invalid email format. Please try again:")
        return EMAIL
    
    # Check available keys
    available_key = session.query(KeyPool).filter_by(used=False).first()
    
    if not available_key:
        await update.message.reply_text("All keys have been claimed! Please check back next month.")
        session.close()
        return ConversationHandler.END
    
    # Save user and assign key
    try:
        new_user = User(
            user_id=user_id,
            first_name=context.user_data['first_name'],
            last_name=context.user_data['last_name'],
            email=email,
            key=available_key.key
        )
        available_key.used = True
        session.add(new_user)
        session.commit()
        
        await update.message.reply_text(
            f"✅ Registration complete!\n"
            f"Your unique key: {available_key.key}\n"
            f"Save this key securely!"
        )
    except Exception as e:
        session.rollback()
        logger.error(f"Database error: {e}")
        await update.message.reply_text("⚠️ An error occurred. Please try again later.")
    finally:
        session.close()
    
    return ConversationHandler.END

def main() -> None:
    # Initialize key pool
    init_keys()
    
    # Create bot application
    application = Application.builder().token(TOKEN).build()
    
    # Conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            FIRST_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_first_name)],
            LAST_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_last_name)],
            EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_email)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    
    application.add_handler(conv_handler)
    application.run_polling()

if __name__ == "__main__":
    main()
