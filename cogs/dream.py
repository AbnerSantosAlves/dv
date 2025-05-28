import discord
from discord.ext import commands
from discord.ext.commands import BucketType, cooldown
import random
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, func
from .database import Base, Usuario, Jogador
from data.jogadores import jogadores_futebol
import requests
from io import BytesIO
from PIL import Image
import os
import re
import asyncio # Adicionado para uso futuro em downloads assíncronos
from discord.ui import Modal, TextInput


# Configuração do banco de dados
engine = create_engine('sqlite:///database.db')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

# Constantes
TAMANHO_CARTA = (140, 180)
posicoes_campo_coordenadas = {
    10001: (330, 610),  # GL - Goleiro  #lado #cima FEITO
    10002: (655, 520),  # LD - Lateral Direito  - LD   FEITO
    10003: (170, 590),  # ZAG1 - Zagueiro Central 1 FEITO
    10004: (490, 590),  # ZAG2 - Zagueiro Central 2 FEITO
    10005: (10, 520),  # LE - Lateral Esquerdo  FEITO
    10006: (335, 400),  # VOL - Volante  #FEITO
    10007: (170, 270),  # MC - Meio-campo Central #FEITO
    10008: (500, 200),  # MO - Meia Ofensivo
    10009: (640, 90),  # PD - Ponta Direita FEITO
    10010: (330, 40),  # CA - Centroavante FEITO
    10011: (20, 90),  # PE - Ponta Esquerda #FEITO
}

LIMITE_JOGADORES_ELENCO = 11  # Constante para o limite de jogadores no elenco

# Cache simples para imagens de cartas baixadas
# Em um projeto maior, considere um sistema de cache mais robusto (ex: LRU Cache)
image_cache = {}

def sanitize_filename(filename):
    """
    Remove caracteres inválidos para nomes de arquivo (especialmente no Windows,
    mas bom para compatibilidade cruzada).
    """
    invalid_chars = r'[\\/:*?"<>|]'
    return re.sub(invalid_chars, '', filename)

class MudarNomeTimeModal(Modal):
    def __init__(self):
        super().__init__(title="Mudança no Time")

        self.nome = TextInput(label="Nome", placeholder="Digite o novo nome do seu time")
        self.add_item(self.nome)


    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True) # Deferir para evitar "Interaction failed"

        with Session() as session:
            try:
                # Use interaction.user.id para obter o ID do usuário que interagiu
                usuario = session.query(Usuario).filter_by(discordId=str(interaction.user.id)).first()

                if not usuario:
                    # Se o usuário não existe, você pode criar um novo ou enviar um erro
                    usuario = Usuario(discordId=str(interaction.user.id), nome_time=self.nome.value)
                    session.add(usuario)
                    await interaction.followup.send("Novo usuário criado e nome do time atualizado com sucesso!", ephemeral=True)
                else:
                    usuario.nome_time = self.nome.value
                    session.add(usuario)
                    await interaction.followup.send("Nome do time atualizado com sucesso!", ephemeral=True)
                session.commit()
            except Exception as e:
                session.rollback() # Reverter a transação em caso de erro
                print(f"Erro ao atualizar nome do time no modal: {e}")
                await interaction.followup.send("Ocorreu um erro ao atualizar o nome do seu time. Tente novamente mais tarde.", ephemeral=True)


class MudarSiglaTimeModal(Modal):
    def __init__(self):
        super().__init__(title="Mudança no Time")

        self.sigla = TextInput(label="Sigla", placeholder="Digite a nova sigla do seu time")
        self.add_item(self.sigla)


    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True) # Deferir para evitar "Interaction failed"

        with Session() as session:
            try:
                # Use interaction.user.id para obter o ID do usuário que interagiu
                usuario = session.query(Usuario).filter_by(discordId=str(interaction.user.id)).first()

                if not usuario:
                    # Se o usuário não existe, você pode criar um novo ou enviar um erro
                    usuario = Usuario(discordId=str(interaction.user.id), nome_time=self.sigla.value)
                    session.add(usuario)
                    await interaction.followup.send("Novo usuário criado e nome do time atualizado com sucesso!", ephemeral=True)
                else:
                    usuario.time_sigla = self.sigla.value
                    session.add(usuario)
                    await interaction.followup.send("Nome do time atualizado com sucesso!", ephemeral=True)
                session.commit()
            except Exception as e:
                session.rollback() # Reverter a transação em caso de erro
                print(f"Erro ao atualizar nome do time no modal: {e}")
                await interaction.followup.send("Ocorreu um erro ao atualizar o nome do seu time. Tente novamente mais tarde.", ephemeral=True)


class MudarTimeButtons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # View persistente

    @discord.ui.button(label="Mudar nome do time", style=discord.ButtonStyle.primary)
    async def botao_nome_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.send_modal(MudarNomeTimeModal())
        except Exception as e:
            await interaction.response.send_message("Você já respondeu ou houve um erro.", ephemeral=True)
            print(f"Erro ao abrir modal: {e}")

    @discord.ui.button(label="Mudar sigla do Time", style=discord.ButtonStyle.primary)
    async def botao_sigla_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.send_modal(MudarSiglaTimeModal())
        except Exception as e:
            await interaction.response.send_message("Você já respondeu ou houve um erro.", ephemeral=True)
            print(f"Erro ao abrir modal: {e}")


class Promover(discord.ui.View):
    def __init__(self, nome, valor, habilidade, posicao, usuario_discord_id, ctx):
        super().__init__(timeout=None)  # View persistente
        
        self.nome = nome
        self.valor = valor
        self.habilidade = habilidade
        self.posicao = posicao
        self.usuario_discord_id = usuario_discord_id
        self.ctx = ctx

    @discord.ui.button(label="Promover", style=discord.ButtonStyle.primary)
    async def promover(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True) # Deferir imediatamente

        # Crie uma nova sessão para esta interação
        with Session() as session:
            usuario = session.query(Usuario).filter_by(discordId=str(self.usuario_discord_id)).first()
            if not usuario:
                await interaction.followup.send("Erro: Usuário não encontrado.", ephemeral=True)
                return

            select = PosicaoSelect(
                nome=self.nome,
                valor=self.valor,
                habilidade=self.habilidade,
                posicao=self.posicao,
                usuario_discord_id=self.usuario_discord_id, # Passa o ID do usuário para o Select
                ctx=self.ctx
            )
            view = discord.ui.View()
            view.add_item(select)
            
            await interaction.followup.send("Escolha a posição para o jogador:", view=view, ephemeral=True)

async def get_player_card_image(url):
    """
    Baixa e armazena em cache a imagem da carta de um jogador.
    """
    if url in image_cache:
        return image_cache[url].copy() # Retorna uma cópia para não modificar a imagem em cache

    try:
        # Usando aiohttp para download assíncrono (melhor performance para muitas requisições)
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()
                image_data = await response.read()
        
        carta = Image.open(BytesIO(image_data)).convert("RGBA")
        image_cache[url] = carta # Armazena em cache
        return carta.copy()
    except requests.exceptions.RequestException as e:
        print(f"Erro ao baixar a imagem da carta ({url}): {e}")
        return None
    except IOError as e:
        print(f"Erro ao abrir a imagem da carta com Pillow ({url}): {e}")
        return None
    except Exception as e:
        print(f"Erro inesperado ao processar carta ({url}): {e}")
        return None




class Dream(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def cofre(self, ctx):
        with Session() as session: # Garante que a sessão é fechada
            usuario = session.query(Usuario).filter_by(discordId=str(ctx.author.id)).first()

            if not usuario:
                usuario = Usuario(discordId=str(ctx.author.id), saldo=0.0, nome_time="Novo Time", time_sigla="NVT", escalacao="4-3-3", valor_time=0.0, estadio="Estádio António Coimbra da Mota")
                session.add(usuario)
                session.commit()
            
            embed = discord.Embed(
                title="Cofre do clube",
                description=
                f"O saldo atual é: **``{usuario.saldo:,.0f}``**\n"
                "Você pode usar esse saldo para contratar novos jogadores e fortalecer o seu elenco! Use m!contratar"
                )
            await ctx.send(embed=embed)

    @commands.command()
    async def time(self, ctx):
        with Session() as session: # Garante que a sessão é fechada
            usuario = session.query(Usuario).filter_by(discordId=str(ctx.author.id)).first()

            if not usuario:
                usuario = Usuario(discordId=str(ctx.author.id), saldo=0.0, nome_time="Novo Time", time_sigla="NVT", escalacao="4-3-3", valor_time=0.0, estadio="Estádio António Coimbra da Mota")
                session.add(usuario)
                session.commit()

            try:
                campo = Image.open("./data/campo.jpeg").convert("RGBA")
            except FileNotFoundError:
                await ctx.send("Erro: Imagem do campo base não encontrada.", ephemeral=True)
                return

            jogadores_no_campo = session.query(Jogador).filter(
                Jogador.usuario_id == usuario.id,
                Jogador.posicao_campo.isnot(None)
            ).all()

            jogadores_possuidos = session.query(Jogador).filter_by(usuario_id=usuario.id).all()
            total_valor_numerico = sum(jogador.valor for jogador in jogadores_possuidos)
            total_jogadores = len(jogadores_possuidos) # Mais eficiente que contar com func.count() se já carregou todos

            total_valor_formatado = ""
            if total_valor_numerico >= 1_000_000:
                total_valor_formatado = f"{total_valor_numerico / 1_000_000:.0f}M"
            elif total_valor_numerico >= 1_000:
                total_valor_formatado = f"{total_valor_numerico / 1_000:.0f}K"
            else:
                total_valor_formatado = str(total_valor_numerico)

            # Preparar tarefas de download assíncronas para as imagens
            download_tasks = []
            jogadores_com_coordenadas = []

            for jogador_atual in jogadores_no_campo:
                posicao_id_num = jogador_atual.posicao_campo
                coordenadas = posicoes_campo_coordenadas.get(posicao_id_num)

                if not coordenadas:
                    print(f"Aviso: Coordenadas não encontradas para o ID de posição: {posicao_id_num} do jogador {jogador_atual.nome}. Pulando este jogador.")
                    continue

                dados_jogador = jogadores_futebol.get(jogador_atual.nome)
                url_carta = dados_jogador.get("imagem") if dados_jogador else None

                if not url_carta:
                    print(f"Aviso: URL da carta não encontrada para o jogador {jogador_atual.nome}. Pulando este jogador.")
                    continue
                
                download_tasks.append(get_player_card_image(url_carta))
                jogadores_com_coordenadas.append((jogador_atual, coordenadas))

            # Executar todos os downloads em paralelo
            if download_tasks:
                cartas_baixadas = await asyncio.gather(*download_tasks)

                for i, (jogador_atual, coordenadas) in enumerate(jogadores_com_coordenadas):
                    carta = cartas_baixadas[i]
                    if carta:
                        carta_redimensionada = carta.resize(TAMANHO_CARTA, Image.LANCZOS)
                        campo.paste(carta_redimensionada, coordenadas, carta_redimensionada)
            
            # Salva a imagem composta temporariamente
            nome_arquivo_temp = f"time_do_{usuario.id}.png"
            caminho_temp = os.path.join("./data", nome_arquivo_temp)

            try:
                campo.save(caminho_temp)
            except Exception as e:
                await ctx.send(f"Erro ao salvar a imagem final do campo: {e}", ephemeral=True)
                return

            # Envia embed com a imagem
            file = discord.File(caminho_temp, filename=nome_arquivo_temp)
            embed = discord.Embed(
                title=f"**[{usuario.time_sigla}] {usuario.nome_time}**\n",
                description=
                f"<:money_mxp:1376577220558196868>Valor: **{total_valor_formatado}**\n"
                f"🏟️Estadio: **{usuario.estadio}**"
            )
            embed.add_field(name="Formação:", value="```4-3-3```", inline=False)
            embed.set_thumbnail(url=ctx.author.avatar.url)
            embed.set_author(name="Vados", icon_url=ctx.bot.user.avatar)
            embed.set_footer(text="MXP developments")
            embed.set_image(url=f"attachment://{nome_arquivo_temp}")

            await ctx.send(embed=embed, file=file, view=MudarTimeButtons())

            try:
                os.remove(caminho_temp) # Limpa o arquivo temporário
            except OSError as e:
                print(f"Erro ao remover arquivo temporário {caminho_temp}: {e}")

    @commands.command()
    async def remover(self, ctx, *, jogador:str):
        with Session() as session:
            usuario = session.query(Usuario).filter_by(discordId=str(ctx.author.id)).first()

            nome_busca = jogador.strip()
            jogador_removido = session.query(Jogador).filter_by(usuario_id=usuario.id, nome=nome_busca).first()


            if not jogador_removido:
                await ctx.send("Não existe nenhum jogador com este nome!")
                return
            
            jogador_removido.posicao_campo = 0
            jogador_removido.titular = None
            session.add(jogador_removido)
            session.commit()
            await ctx.send(f"O jogador {jogador} acaba de ser removido dos titulares")

    @commands.command()
    async def promover(self, ctx, *, jogador:str):
        with Session() as session:
            usuario = session.query(Usuario).filter_by(discordId=str(ctx.author.id)).first()

            if not usuario:
                usuario = Usuario(discordId=str(ctx.author.id), saldo=0.0, nome_time="Novo Time", time_sigla="NVT", escalacao="4-3-3", valor_time=0.0, estadio="Estádio António Coimbra da Mota")
                session.add(usuario)
                session.commit()
            

            nome_busca = jogador.strip().upper()
            jogador = session.query(Jogador).filter_by(usuario_id=usuario.id, nome=nome_busca).first()

            if not jogador:
                await ctx.send("Espera! Você não tem esse jogador.")
                return

            nome = jogador.nome
            valor = jogador.valor
            habilidade = jogador.habilidade
            posicao = jogador.posicao

            await ctx.send(view=Promover(nome, valor, habilidade, posicao, usuario.discordId, ctx))



    @commands.command()
    async def obter(self, ctx):
        with Session() as session: # Garante que a sessão é fechada
            usuario = session.query(Usuario).filter_by(discordId=str(ctx.author.id)).first()

            if not usuario:
                usuario = Usuario(discordId=str(ctx.author.id), saldo=0.0, nome_time="Novo Time", time_sigla="NVT", escalacao="4-3-3", valor_time=0.0, estadio="Estádio António Coimbra da Mota")
                session.add(usuario)
                session.commit()
            
            # Obter os nomes dos jogadores que o usuário já possui
            # Carrega todos os jogadores do usuário de uma vez
            jogadores_possuidos_db = session.query(Jogador.nome).filter_by(usuario_id=usuario.id).all()
            nomes_jogadores_usuario = {j.nome for j in jogadores_possuidos_db} # Usar set para busca mais rápida

            # Filtrar jogadores que o usuário ainda não possui
            jogadores_disponiveis = {
                nome: dados for nome, dados in jogadores_futebol.items()
                if nome not in nomes_jogadores_usuario
            }
            
            if not jogadores_disponiveis:
                await ctx.send("Carambolas, você tem todos os jogadores.")
                return

            nome, dados_novo = random.choice(list(jogadores_disponiveis.items()))
            valor = dados_novo['preco']
            habilidade = dados_novo['habilidade']
            posicao = dados_novo['posicao']
            imagem = dados_novo['imagem']
            colecao = dados_novo['colecao']

            if colecao == "Comum":
                emoji = "<:comummxp:1376541822867865600>"
            if colecao == "Lendas":
                emoji = "<:lendasmxp:1376541245635301477>"
            if colecao == "Base":
                emoji = "<:comummxp:1376541822867865600>"


            novo_jogador = Jogador(nome=nome, valor=valor, habilidade=habilidade, posicao=posicao, usuario_id=usuario.id, posicao_campo=0.0)
            session.add(novo_jogador)
            session.commit()

            embed = discord.Embed(
                title=f"O {posicao} {emoji} {nome} chegou de graça ao seu elenco!",
                description=f"**Valor de Mercado:** ``{valor:,.0f} reais``\n**Habilidade:** ``{habilidade}``\n**Coleção:** ``{dados_novo.get('colecao', 'N/A')}``", # Adicionei .get para colecao caso não exista
                color=discord.Color.blue()
            )
            embed.set_image(url=imagem)
            # Passa apenas o ID do usuário para evitar problemas de sessão
            view = ObterOpcoes(nome, valor, habilidade, posicao, usuario.discordId, ctx)
            await ctx.send(embed=embed, view=view)
    
    @commands.command()
    async def elenco(self, ctx):
        with Session() as session: # Garante que a sessão é fechada
            usuario = session.query(Usuario).filter_by(discordId=str(ctx.author.id)).first()

            if not usuario:
                await ctx.send("Parece que você ainda não tem jogadores. Use `m!obter` para conseguir um!")
                return # Sai cedo se o usuário não existe

            # Carrega os jogadores relacionados ao usuário. SQLAlchemy faz isso eficientemente se 'jogadores' for uma relação.
            # Se 'jogadores' não for uma relação carregada, é melhor fazer uma consulta explícita:
            jogadores_possuidos = session.query(Jogador).filter_by(usuario_id=usuario.id).all()
            
            if not jogadores_possuidos: # Verifica se a lista está vazia
                await ctx.send("Parece que você ainda não tem jogadores. Use `m!obter` para conseguir um!")
                return

            total_valor_numerico = sum(jogador.valor for jogador in jogadores_possuidos)
            total_jogadores = len(jogadores_possuidos)

            total_valor_formatado = ""
            if total_valor_numerico >= 1_000_000:
                total_valor_formatado = f"{total_valor_numerico / 1_000_000:.0f}M"
            elif total_valor_numerico >= 1_000:
                total_valor_formatado = f"{total_valor_numerico / 1_000:.0f}K"
            else:
                total_valor_formatado = str(total_valor_numerico)
            
            embed = discord.Embed(
                title=f"⚽ {usuario.nome_time}",
                description=
                f"*Valor:* {total_valor_formatado}\n"
                f"*Nº Jogadores:* {total_jogadores}",
                color=discord.Color.blue()
            )
            for i, j in enumerate(jogadores_possuidos): # Itera sobre a lista carregada
                status = f"(Titular: {j.titular})" if j.titular else "(Reserva)"
                embed.add_field(name=f"#{i+1} - {j.nome}", value=f"Posição: {j.posicao} | Habilidade: {j.habilidade} {status}", inline=False)
            
            await ctx.send(embed=embed)



### Classes de Interação (Botões e Selects)


import aiohttp # Adicionado para download assíncrono

class ObterOpcoes(discord.ui.View):
    def __init__(self, nome, valor, habilidade, posicao, usuario_discord_id, ctx):
        super().__init__()
        self.nome = nome
        self.valor = valor
        self.habilidade = habilidade
        self.posicao = posicao
        self.usuario_discord_id = usuario_discord_id # Passamos apenas o ID do usuário
        self.ctx = ctx

    @discord.ui.button(label="Promover", style=discord.ButtonStyle.primary)
    async def promover(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True) # Deferir imediatamente

        # Crie uma nova sessão para esta interação
        with Session() as session:
            usuario = session.query(Usuario).filter_by(discordId=str(self.usuario_discord_id)).first()
            if not usuario:
                await interaction.followup.send("Erro: Usuário não encontrado.", ephemeral=True)
                return

            select = PosicaoSelect(
                nome=self.nome,
                valor=self.valor,
                habilidade=self.habilidade,
                posicao=self.posicao,
                usuario_discord_id=self.usuario_discord_id, # Passa o ID do usuário para o Select
                ctx=self.ctx
            )
            view = discord.ui.View()
            view.add_item(select)
            
            await interaction.followup.send("Escolha a posição para o jogador:", view=view, ephemeral=True)

    @discord.ui.button(label="Vender", style=discord.ButtonStyle.danger)
    async def vender(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Crie uma nova sessão para esta interação
        with Session() as session:
            usuario = session.query(Usuario).filter_by(discordId=str(self.usuario_discord_id)).first()
            if not usuario:
                await interaction.response.send_message("Erro: Usuário não encontrado.", ephemeral=True)
                return

            jogador_para_vender = session.query(Jogador).filter_by(
                usuario_id=usuario.id,
                nome=self.nome,
                posicao=self.posicao,
                habilidade=self.habilidade
            ).first()

            if jogador_para_vender:
                usuario.saldo += jogador_para_vender.valor
                session.delete(jogador_para_vender)
                session.commit()
                await interaction.response.send_message(
                    f"✅ Você vendeu **{self.nome}** por ``R$ {jogador_para_vender.valor:,.0f}``!\nSaldo atual: ``R$ {usuario.saldo:,.0f}``",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "❌ O jogador não foi encontrado no seu elenco para venda.",
                    ephemeral=True
                )

class PosicaoSelect(discord.ui.Select):
    def __init__(self, nome, valor, habilidade, posicao, usuario_discord_id, ctx):
        self.nome = nome
        self.valor = valor
        self.habilidade = habilidade
        self.posicao = posicao
        self.usuario_discord_id = usuario_discord_id # Recebe o ID do usuário
        self.ctx = ctx

        options = [
            discord.SelectOption(label="GL", description="Goleiro", value="GL"),
            discord.SelectOption(label="LD", description="Lateral Direito", value="LD"),
            discord.SelectOption(label="ZAG1", description="Zagueiro Central 1", value="ZAG1"),
            discord.SelectOption(label="ZAG2", description="Zagueiro Central 2", value="ZAG2"),
            discord.SelectOption(label="LE", description="Lateral Esquerdo", value="LE"),
            discord.SelectOption(label="VOL", description="Volante", value="VOL"),
            discord.SelectOption(label="MC", description="Meio-campo Central", value="MC"),
            discord.SelectOption(label="MO", description="Meia Ofensivo", value="MO"),
            discord.SelectOption(label="PD", description="Ponta Direita", value="PD"),
            discord.SelectOption(label="CA", description="Centroavante", value="CA"),
            discord.SelectOption(label="PE", description="Ponta Esquerda", value="PE"),
        ]
        
        super().__init__(
            placeholder="Escolha a posição...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True) # Deferir imediatamente
        escolha = self.values[0]

        # Crie uma nova sessão para este callback
        with Session() as session:
            usuario = session.query(Usuario).filter_by(discordId=str(self.usuario_discord_id)).first()
            if not usuario:
                await interaction.followup.send("Erro: Usuário não encontrado.", ephemeral=True)
                return

            jogador_no_elenco = session.query(Jogador).filter_by(
                usuario_id=usuario.id,
                nome=self.nome,
                posicao=self.posicao,
                habilidade=self.habilidade
            ).first()

            if not jogador_no_elenco:
                await interaction.followup.send("Jogador não encontrado no elenco. Por favor, tente novamente.", ephemeral=True)
                return

            posicoes_map_escolha_para_id = {
                "GL": 10001, "LD": 10002, "ZAG1": 10003, "ZAG2": 10004,
                "LE": 10005, "VOL": 10006, "MC": 10007, "MO": 10008,
                "PD": 10009, "CA": 10010, "PE": 10011,
            }

            jogador_no_elenco.posicao_campo = posicoes_map_escolha_para_id.get(escolha)
            jogador_no_elenco.titular = "Titular"

            if jogador_no_elenco.posicao_campo is None:
                await interaction.followup.send("Erro: Escolha de posição inválida. Por favor, selecione uma posição válida.", ephemeral=True)
                return

            try:
                session.add(jogador_no_elenco)
                session.commit()
            except Exception as e:
                session.rollback()
                await interaction.followup.send(f"Erro ao salvar a posição do jogador no banco de dados: {e}", ephemeral=True)
                return

            try:
                campo = Image.open("./data/campo.jpeg").convert("RGBA")
            except FileNotFoundError:
                await interaction.followup.send("Erro: Imagem do campo base não encontrada.", ephemeral=True)
                return

            jogadores_no_campo = session.query(Jogador).filter(
                Jogador.usuario_id == usuario.id,
                Jogador.posicao_campo.isnot(None)
            ).all()

            if not jogadores_no_campo:
                await interaction.followup.send("Nenhum jogador está posicionado no seu time ainda para exibir no campo.", ephemeral=True)
                return

            download_tasks = []
            jogadores_com_coordenadas = []

            for jogador_atual in jogadores_no_campo:
                posicao_id_num = jogador_atual.posicao_campo
                coordenadas = posicoes_campo_coordenadas.get(posicao_id_num)

                if not coordenadas:
                    print(f"Aviso: Coordenadas não encontradas para o ID de posição: {posicao_id_num} do jogador {jogador_atual.nome}. Pulando este jogador.")
                    continue

                dados_jogador = jogadores_futebol.get(jogador_atual.nome)
                url_carta = dados_jogador.get("imagem") if dados_jogador else None

                if not url_carta:
                    print(f"Aviso: URL da carta não encontrada para o jogador {jogador_atual.nome}. Pulando este jogador.")
                    continue
                
                download_tasks.append(get_player_card_image(url_carta))
                jogadores_com_coordenadas.append((jogador_atual, coordenadas))

            if download_tasks:
                cartas_baixadas = await asyncio.gather(*download_tasks)

                for i, (jogador_atual, coordenadas) in enumerate(jogadores_com_coordenadas):
                    carta = cartas_baixadas[i]
                    if carta:
                        carta_redimensionada = carta.resize(TAMANHO_CARTA, Image.LANCZOS)
                        campo.paste(carta_redimensionada, coordenadas, carta_redimensionada)

            nome_arquivo_temp = f"time_do_{usuario.id}.png"
            caminho_temp = os.path.join("./data", nome_arquivo_temp)

            try:
                campo.save(caminho_temp)
            except Exception as e:
                await interaction.followup.send(f"Erro ao salvar a imagem final do campo: {e}", ephemeral=True)
                return

            file = discord.File(caminho_temp, filename=nome_arquivo_temp)
            embed = discord.Embed(
                title=f"⚽ Posição de {jogador_no_elenco.nome} atualizada!",
                description="Seu time em campo com todos os jogadores posicionados.",
                color=discord.Color.green()
            )
            embed.set_image(url=f"attachment://{nome_arquivo_temp}")
            embed.set_footer(text=f"Posicionado por: {interaction.user.display_name}")

            try:
                await interaction.followup.send(file=file, embed=embed)
            except Exception as e:
                print(f"Erro ao enviar mensagem de interação para {interaction.user.display_name}: {e}")
                await interaction.channel.send(f"Desculpe, {interaction.user.display_name}, não consegui enviar a imagem do seu time agora. Erro: {e}")

            try:
                os.remove(caminho_temp)
            except OSError as e:
                print(f"Erro ao remover arquivo temporário {caminho_temp}: {e}")


async def setup(bot):
    await bot.add_cog(Dream(bot))