import antigravity  # 🚀 Clin d'œil

import os
import re
import uuid
from typing import Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, HTTPException, Response, Depends
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import httpx

from sqlalchemy import String, Text, ForeignKey, DateTime, Boolean, Float, Integer, UniqueConstraint, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# 1. BASE DE DONNÉES SQLITE ASYNCHRONE
class Base(DeclarativeBase):
    pass

class Merchant(Base):
    __tablename__ = "merchants"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    whatsapp_phone_number_id: Mapped[str] = mapped_column(String(50), unique=True)
    whatsapp_access_token: Mapped[str] = mapped_column(String(255), default="DEMO_TOKEN")
    whatsapp_verify_token: Mapped[str] = mapped_column(String(100), default="mon_token_secret_meta_2026")
    system_prompt_override: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    products: Mapped[List["Product"]] = relationship("Product", back_populates="merchant", lazy="selectin")

class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    merchant_id: Mapped[int] = mapped_column(Integer, ForeignKey("merchants.id"))
    name: Mapped[str] = mapped_column(String(150))
    description: Mapped[Optional[str]] = mapped_column(Text)
    price: Mapped[float] = mapped_column(Float)
    stock_quantity: Mapped[int] = mapped_column(Integer, default=10)
    merchant: Mapped["Merchant"] = relationship("Merchant", back_populates="products")

class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    merchant_id: Mapped[int] = mapped_column(Integer, ForeignKey("merchants.id"))
    whatsapp_number: Mapped[str] = mapped_column(String(30))
    profile_name: Mapped[Optional[str]] = mapped_column(String(100))
    __table_args__ = (UniqueConstraint("merchant_id", "whatsapp_number", name="uq_cust"),)

class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(Integer, ForeignKey("customers.id"))
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

engine = create_async_engine("sqlite+aiosqlite:///./whatsapp_saas.db", echo=False)
AsyncSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

async def get_db():
    async with AsyncSessionLocal() as s:
        yield s

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(Merchant).where(Merchant.whatsapp_phone_number_id == "109876543210987"))
        if not res.scalar_one_or_none():
            m = Merchant(
                name="Boutique Prestige Niamey",
                whatsapp_phone_number_id="109876543210987",
                system_prompt_override="Tu es l'agent commercial IA sur WhatsApp. Conclus les ventes avec le lien de paiement."
            )
            session.add(m)
            await session.flush()
            session.add_all([
                Product(merchant_id=m.id, name="Montre Chrono Acier", description="Mouvement automatique suisse, étanche.", price=25000.0, stock_quantity=10),
                Product(merchant_id=m.id, name="Costume Slim Prestige", description="Tissu italien respirant.", price=45000.0, stock_quantity=5),
                Product(merchant_id=m.id, name="Chaussures Cuir Oxford", description="Cuir véritable fait main.", price=30000.0, stock_quantity=8),
            ])
            await session.commit()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(title="WhatsApp Business SaaS", lifespan=lifespan)

# 2. SIMULATEUR WHATSAPP & IA DE VENTE
class WebMsg(BaseModel):
    message: str
    phone: str = "22790112233"

@app.post("/api/simulate")
async def simulate_chat(body: WebMsg, db: AsyncSession = Depends(get_db)):
    tx_ref = f"CMD-{uuid.uuid4().hex[:6].upper()}"
    msg_l = body.message.lower()

    if any(k in msg_l for k in ["montre", "25000", "chrono", "prix", "acheter"]):
        pay_url = f"https://pay.owopay.com/checkout/chk_{tx_ref}?amt=25000"
        reply = (
            f"Très bon choix ! Notre *Montre Chrono Acier* est disponible au prix de 25 000 FCFA.\n\n"
            f"👉 Cliquez ici pour régler par Mobile Money (Wave / Zamani / Moov) :\n"
            f"{pay_url}\n\n"
            f"Livraison en 2h chrono !"
        )
    elif "costume" in msg_l:
        pay_url = f"https://pay.owopay.com/checkout/chk_{tx_ref}?amt=45000"
        reply = f"Notre *Costume Slim Prestige* italien est à 45 000 FCFA.\n\n👉 Réglez votre commande ici : {pay_url}"
    else:
        reply = (
            "Bonjour ! Bienvenue chez Boutique Prestige.\n"
            "Nous avons en stock : Montre Chrono (25 000 FCFA), Costume Slim (45 000 FCFA) et Chaussures Cuir (30 000 FCFA). Quel article souhaitez-vous commander ?"
        )
    return {"reply": reply}

@app.get("/webhook")
async def verify_webhook(hub_mode: str = Query(None, alias="hub.mode"), hub_verify_token: str = Query(None, alias="hub.verify_token"), hub_challenge: str = Query(None, alias="hub.challenge")):
    if hub_mode == "subscribe" and hub_verify_token == "mon_token_secret_meta_2026":
        return Response(content=hub_challenge, media_type="text/plain")
    raise HTTPException(status_code=403, detail="Token invalide")

@app.get("/", response_class=HTMLResponse)
async def home():
    return """
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <title>Simulateur WhatsApp Business SaaS</title>
        <style>
            * { box-sizing: border-box; margin: 0; padding: 0; font-family: sans-serif; }
            body { background: #0f172a; color: white; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100vh; padding: 20px; }
            .phone { width: 100%; max-width: 420px; background: #1e293b; border-radius: 20px; overflow: hidden; height: 600px; display: flex; flex-direction: column; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
            .header { background: #075e54; padding: 15px; font-weight: bold; font-size: 16px; }
            .chat { flex: 1; padding: 15px; background: #0b141a; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; }
            .msg { max-width: 80%; padding: 10px 14px; border-radius: 10px; font-size: 14px; line-height: 1.4; }
            .bot { background: #202c33; align-self: flex-start; }
            .bot a { color: #53bdeb; font-weight: bold; word-break: break-all; }
            .user { background: #005c4b; align-self: flex-end; }
            .footer { display: flex; padding: 10px; background: #202c33; gap: 8px; }
            input { flex: 1; padding: 10px; border-radius: 20px; border: none; outline: none; background: #2a3942; color: white; }
            button { padding: 10px 16px; border-radius: 20px; border: none; background: #00a884; color: white; cursor: pointer; font-weight: bold; }
        </style>
    </head>
    <body>
        <div class="phone">
            <div class="header">🛍️ Boutique Prestige Niamey (Vendeur IA)</div>
            <div class="chat" id="chat">
                <div class="msg bot">Bonjour ! Bienvenue chez Boutique Prestige. Quel produit vous intéresse (Montres, Costumes, Chaussures) ?</div>
            </div>
            <div class="footer">
                <input type="text" id="input" placeholder="Écrivez un message (ex: Je veux la montre)..." onkeypress="if(event.key==='Enter') send()">
                <button onclick="send()">Envoyer</button>
            </div>
        </div>
        <script>
            async function send() {
                const inp = document.getElementById("input");
                const val = inp.value.trim();
                if (!val) return;
                const chat = document.getElementById("chat");
                chat.innerHTML += `<div class="msg user">${val}</div>`;
                inp.value = "";
                chat.scrollTop = chat.scrollHeight;
                const res = await fetch("/api/simulate", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ message: val })
                });
                const data = await res.json();
                let reply = data.reply.replace(/(https?:\\/\\/[^\\s]+)/g, '<a href="$1" target="_blank">$1</a>');
                chat.innerHTML += `<div class="msg bot">${reply}</div>`;
                chat.scrollTop = chat.scrollHeight;
            }
        </script>
    </body>
    </html>
    """
