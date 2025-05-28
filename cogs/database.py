from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
import locale
from discord.ext import commands



class DatabaseCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

db = create_engine("sqlite:///database.db")
Seesion = sessionmaker(bind=db)
session = Seesion()

Base = declarative_base()

class Usuario(Base):
    __tablename__ = "usuarios"
    id = Column("id", Integer, primary_key=True, autoincrement=True)
    discordId = Column("discordId", Integer)
    saldo = Column("saldo", Float)
    nome_time = Column("nome_time", String)
    time_sigla = Column("time_sigla", String)
    escalacao = Column("time_escalacao", String)
    valor_time = Column("valor", Float, default=0.0)
    estadio = Column("estadio", String)

    jogadores = relationship("Jogador", back_populates="usuario")
    

    def __init__(self, discordId, saldo, nome_time, time_sigla, valor_time, escalacao, estadio): #Essa função deve ser carregada sempre ao usar uma classe no python. Através dela, você deve passar os parâmetros que terá na classe.
        self.discordId = discordId
        self.saldo = saldo
        self.nome_time = nome_time
        self.time_sigla = time_sigla
        self.valor_time = valor_time
        self.escalacao = escalacao
        self.estadio = estadio

class Jogador(Base):
    __tablename__ = "jogadores"
    id = Column("id", Integer, primary_key=True, autoincrement= True)
    nome = Column("nome", String)
    valor = Column("valor", Float)
    habilidade = Column("habilidade", Integer)
    posicao = Column("posicao", String)
    usuario_id = Column(Integer, ForeignKey('usuarios.id'))
    titular = Column("titular", String, default=None)
    posicao_campo = Column("posicao_campo", Float)

    usuario = relationship("Usuario", back_populates="jogadores")

    
    def __init__(self, nome, valor, habilidade, posicao, usuario_id, posicao_campo): #Essa função deve ser carregada sempre ao usar uma classe no python. Através dela, você deve passar os parâmetros que terá na classe.
        self.nome = nome
        self.valor = valor
        self.habilidade = habilidade
        self.posicao = posicao
        self.usuario_id = usuario_id
        self.posicao_campo = posicao_campo

async def setup(bot):
    await bot.add_cog(DatabaseCog(bot))