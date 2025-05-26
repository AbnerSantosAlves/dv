from discord.ext import commands
from sqlalchemy import Column, Integer, String, Float, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

class DatabaseCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

Base = declarative_base()

class Usuario(Base):
    __tablename__ = 'usuarios'
    id = Column(Integer, primary_key=True)
    discord_id = Column(String, unique=True)
    saldo = Column(Float, default=0.0)

    jogadores = relationship('JogadorUsuario', back_populates='usuario')

class JogadorUsuario(Base):
    __tablename__ = 'jogadores_usuario'
    id = Column(Integer, primary_key=True)
    nome = Column(String)
    posicao = Column(String)
    habilidade = Column(Integer)
    preco = Column(Float)
    titular = Column(String, default=None)  # Ex: 'GO', 'ZAG'

    usuario_id = Column(Integer, ForeignKey('usuarios.id'))
    usuario = relationship('Usuario', back_populates='jogadores')


async def setup(bot):
    await bot.add_cog(DatabaseCog(bot))