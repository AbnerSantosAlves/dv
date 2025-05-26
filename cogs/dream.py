import discord
from discord.ext import commands
from discord.ext.commands import BucketType, cooldown
import random
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from .database import Base, Usuario, JogadorUsuario # Certifique-se de que database está no mesmo nível ou acessível
from data.jogadores import jogadores_futebol
import math 

engine = create_engine('sqlite:///dream.db')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

LIMITE_JOGADORES_ELENCO = 11 # Constante para o limite de jogadores no elenco

class Dream(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="cofre")
    async def ver_saldo(self, ctx):
        session = Session()
        usuario = session.query(Usuario).filter_by(discord_id=str(ctx.author.id)).first()

        if not usuario:
            usuario = Usuario(discord_id=str(ctx.author.id), saldo=0.0)
            session.add(usuario)
            session.commit()

        embed = discord.Embed(
            title="Cofre do clube",
            description=
            f"O saldo atual é: **``{usuario.saldo:,.0f}``**\n"
            "Você pode usar esse saldo para contratar novos jogadores e fortalecer o seu elenco! Use m!contratar"
            )
        await ctx.send(embed=embed)
        session.close()

    @commands.command(name="titulares")
    async def ver_titulares(self, ctx):
        session = Session()
        usuario = session.query(Usuario).filter_by(discord_id=str(ctx.author.id)).first()

        if not usuario:
            await ctx.send("⚠️ Você ainda não possui nenhum jogador.")
            session.close()
            return

        jogadores = session.query(JogadorUsuario).filter_by(usuario_id=usuario.id).filter(JogadorUsuario.titular != None).all()

        if not jogadores:
            await ctx.send("🛑 Nenhum jogador foi escalado como titular.")
            session.close()
            return

        embed = discord.Embed(title="📋 Escalação Atual", color=discord.Color.green())
        for j in jogadores:
            embed.add_field(name=f"{j.titular} - {j.nome}", value=f"Habilidade: {j.habilidade}", inline=False)

        await ctx.send(embed=embed)
        session.close()

    @commands.command(name="loja")
    async def ver_loja(self, ctx):
        embed = discord.Embed(
            title="🛒 Loja",
            description="(em breve) Você poderá comprar melhorias para seu time, visuais, boosts e mais!",
            color=discord.Color.purple()
        )
        embed.set_footer(text="Use m!saldo para ver seu dinheiro.")
        await ctx.send(embed=embed)

    @commands.command(name="elenco") # Novo comando para ver todos os jogadores
    async def ver_elenco(self, ctx):
        session = Session()
        usuario = session.query(Usuario).filter_by(discord_id=str(ctx.author.id)).first()

        if not usuario or not usuario.jogadores:
            await ctx.send("⚠️ Você ainda não possui nenhum jogador no seu elenco.")
            session.close()
            return

        embed = discord.Embed(title="⚽ Seu Elenco", color=discord.Color.blue())
        for i, j in enumerate(usuario.jogadores):
            status = f"(Titular: {j.titular})" if j.titular else "(Reserva)"
            embed.add_field(name=f"#{i+1} - {j.nome}", value=f"Posição: {j.posicao} | Habilidade: {j.habilidade} {status}", inline=False)

        await ctx.send(embed=embed)
        session.close()

    @commands.command(name="obter")
    @commands.cooldown(rate=1, per=3600, type=commands.BucketType.user)
    async def obter_jogador(self, ctx):
        session = Session()
        autor_id = str(ctx.author.id)

        usuario = session.query(Usuario).filter_by(discord_id=autor_id).first()
        if not usuario:
            usuario = Usuario(discord_id=autor_id)
            session.add(usuario)
            session.commit()

        # Obter os nomes dos jogadores que o usuário já possui
        jogadores_do_usuario_db = session.query(JogadorUsuario).filter_by(usuario_id=usuario.id).all()
        nomes_jogadores_usuario = [jogador.nome for jogador in jogadores_do_usuario_db]

        # Filtrar jogadores que o usuário ainda não possui
        jogadores_disponiveis = {
            nome: dados for nome, dados in jogadores_futebol.items()
            if nome not in nomes_jogadores_usuario
        }

        if not jogadores_disponiveis:
            await ctx.send("Carambolas, você tem todos os jogadore.")
            session.close()
            return

        nome_novo, dados_novo = random.choice(list(jogadores_disponiveis.items()))
        preco_novo = dados_novo['preco']
        habilidade_novo = dados_novo['habilidade']
        posicao_novo = dados_novo['posicao']
        imagem = dados_novo['imagem']
        colecao = dados_novo['colecao']

        # --- Lógica de limite de elenco ---
        contagem_jogadores_elenco = len(jogadores_do_usuario_db) # Usa a lista já obtida

        if contagem_jogadores_elenco >= LIMITE_JOGADORES_ELENCO:
            # Caso o elenco esteja cheio, permite a substituição
            embed = discord.Embed(
                title=f"🚨 Elenco Cheio! Você obteve {nome_novo}!",
                description=(
                    f"Seu time já atingiu o limite de {LIMITE_JOGADORES_ELENCO} jogadores.\n"
                    f"Você precisa **substituir** um jogador existente por **{nome_novo}** (Habilidade: {habilidade_novo}, Posição: {posicao_novo})."
                ),
                color=discord.Color.red()
            )
            embed.set_footer(text="Selecione o jogador que será substituído no seu elenco.")

            # Cria a view para seleção do jogador a ser substituído
            view = SubstituirJogadorElencoView(
                usuario_id=ctx.author.id,
                novo_jogador_data={'nome': nome_novo, 'posicao': posicao_novo, 'habilidade': habilidade_novo, 'preco': preco_novo},
                jogadores_existentes=jogadores_do_usuario_db # Passa os objetos JogadorUsuario para a view
            )
            await ctx.send(embed=embed, view=view)

        else:
            # Caso o elenco não esteja cheio, adiciona o jogador normalmente
            novo_jogador = JogadorUsuario(
                nome=nome_novo,
                posicao=posicao_novo,
                habilidade=habilidade_novo,
                preco=preco_novo,
                titular=None,
                usuario_id=usuario.id
            )
            session.add(novo_jogador)
            session.commit()

            embed = discord.Embed(
                title=f"O {posicao_novo} {nome_novo} chegou de graça ao seu elenco!",
                description=f"**Valor de Mercado:** ``{preco_novo:,.0f} reais``\n**Habilidade:** ``{habilidade_novo}``\n**Coleção:** ``{colecao}``",
                color=discord.Color.blue()
            )
            embed.set_image(url=imagem)

            view = OpcoesJogadorView(nome_novo, posicao_novo, preco_novo, habilidade_novo, ctx.author.id)
            await ctx.send(embed=embed, view=view)

        session.close()


    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            minutes = math.ceil(error.retry_after / 60)
            await ctx.send(f"Calma! Há um cooldown de 1 hora para obter jogadores.. Tente novamente em {minutes} minuto{'s' if minutes > 1 else ''}.")
        else:
            raise error
# --- Views de Interação ---

class OpcoesJogadorView(discord.ui.View):
    def __init__(self, nome, posicao, preco, habilidade, dono_id):
        super().__init__(timeout=60)
        self.nome = nome
        self.posicao = posicao
        self.preco = preco
        self.habilidade = habilidade
        self.dono_id = dono_id

    async def interaction_check(self, interaction: discord.Interaction):
        return interaction.user.id == self.dono_id

    @discord.ui.button(label="Vender", style=discord.ButtonStyle.success)
    async def vender(self, interaction: discord.Interaction, button: discord.ui.Button):
        session = Session()
        usuario = session.query(Usuario).filter_by(discord_id=str(interaction.user.id)).first()

        jogador_para_vender = session.query(JogadorUsuario).filter_by(
            usuario_id=usuario.id,
            nome=self.nome,
            posicao=self.posicao,
            habilidade=self.habilidade
            # Não use preco aqui, pois o preço pode mudar no futuro ou ter flutuações,
            # e a intenção é vender o jogador pelo nome, posição e habilidade que foi obtido.
        ).first()

        if jogador_para_vender:
            usuario.saldo += jogador_para_vender.preco # Usa o preço do jogador no DB
            session.delete(jogador_para_vender)
            session.commit()
            await interaction.response.send_message(
                f"✅ Você vendeu **{self.nome}** por ``R$ {jogador_para_vender.preco:,.0f}``!\nSaldo atual: ``R$ {usuario.saldo:,.0f}``",
                ephemeral=True
            )
        else:
            await interaction.response.send_message("❌ O jogador não foi encontrado no seu elenco para venda.", ephemeral=True)

        session.close()

    @discord.ui.button(label="Promover a titular", style=discord.ButtonStyle.primary)
    async def promover(self, interaction: discord.Interaction, button: discord.ui.Button):
        session = Session()
        usuario = session.query(Usuario).filter_by(discord_id=str(interaction.user.id)).first()

        # Encontrar o jogador que está sendo promovido (que já deve estar no elenco do usuário)
        jogador_sendo_promovido = session.query(JogadorUsuario).filter_by(
            usuario_id=usuario.id,
            nome=self.nome,
            posicao=self.posicao,
            habilidade=self.habilidade
        ).first()

        if not jogador_sendo_promovido:
            await interaction.response.send_message(f"❌ O jogador {self.nome} não foi encontrado no seu elenco para promoção.", ephemeral=True)
            session.close()
            return

        # Obter todas as posições titulares e as ocupadas
        posicoes_disponiveis_formacao = ['GO', 'ZAG', 'LE', 'LD', 'MC', 'ATA'] # Exemplo de posições
        jogadores_titulares_do_usuario = session.query(JogadorUsuario).filter_by(
            usuario_id=usuario.id
        ).filter(JogadorUsuario.titular != None).all()
        
        ocupadas = [j.titular for j in jogadores_titulares_do_usuario]
        vagas = [p for p in posicoes_disponiveis_formacao if p not in ocupadas]

        if jogador_sendo_promovido.titular: # Se o jogador já é titular
            await interaction.response.send_message(f"❌ {self.nome} já é titular na posição {jogador_sendo_promovido.titular}!", ephemeral=True)
            session.close()
            return

        if vagas: # Se há vagas de titular
            select = PosicaoSelect(
                nome=self.nome,
                posicao_original=self.posicao,
                habilidade=self.habilidade,
                preco=self.preco,
                vagas=vagas,
                usuario=usuario
            )
            view = discord.ui.View()
            view.add_item(select)
            await interaction.response.send_message("Selecione a posição para escalar o jogador:", view=view, ephemeral=True)

        else: # Se não há vagas de titular (11 titulares já estão escalados)
            # Prepara a lista de jogadores titulares para a substituição
            opcoes_substituicao = []
            for j in jogadores_titulares_do_usuario:
                opcoes_substituicao.append(discord.SelectOption(
                    label=f"{j.titular} - {j.nome} (Habilidade: {j.habilidade})",
                    value=str(j.id) # Usar o ID do jogador para identificar unicamente
                ))

            if not opcoes_substituicao: # Salvaguarda, não deve acontecer se a condição "vagas" for falsa
                await interaction.response.send_message("❌ Não há jogadores titulares para substituir.", ephemeral=True)
                session.close()
                return

            select = SubstituirTitularSelect(
                jogador_sendo_promovido_id=jogador_sendo_promovido.id,
                opcoes_substituicao=opcoes_substituicao,
                usuario_id=usuario.id
            )
            view = discord.ui.View()
            view.add_item(select)
            await interaction.response.send_message(
                f"🚨 Todas as posições de titular estão preenchidas! Escolha qual jogador **titular** você deseja **substituir** por **{self.nome}**:",
                view=view,
                ephemeral=True
            )
        session.close()

class PosicaoSelect(discord.ui.Select):
    def __init__(self, nome, posicao_original, habilidade, preco, vagas, usuario):
        options = [discord.SelectOption(label=v, value=v) for v in vagas]
        super().__init__(placeholder="Escolha uma posição...", min_values=1, max_values=1, options=options)
        self.nome = nome
        self.posicao_original = posicao_original
        self.habilidade = habilidade
        self.preco = preco
        self.usuario = usuario

    async def callback(self, interaction: discord.Interaction):
        session = Session()

        jogador_no_elenco = session.query(JogadorUsuario).filter_by(
            usuario_id=self.usuario.id,
            nome=self.nome,
            posicao=self.posicao_original, # Usar posicao_original para encontrar o jogador que está sendo promovido
            habilidade=self.habilidade
        ).first()

        if jogador_no_elenco:
            jogador_no_elenco.titular = self.values[0] # Define a nova posição titular
            session.commit()

            embed = discord.Embed(title="JOGADOR PROMOVIDO!", description=f"{self.nome} é o novo {self.values[0]} do seu time!")
            embed.set_image(url="https://via.placeholder.com/500x300.png")
            await interaction.response.send_message(embed=embed, ephemeral=False)
        else:
            await interaction.response.send_message(f"❌ Erro: O jogador {self.nome} não foi encontrado no seu elenco para ser promovido.", ephemeral=True)

        session.close()

# --- Nova View para Substituição de Jogadores no Elenco (Comando 'obter') ---
class SubstituirJogadorElencoView(discord.ui.View):
    def __init__(self, usuario_id, novo_jogador_data, jogadores_existentes):
        super().__init__(timeout=120) # Aumentei o timeout para 2 minutos
        self.usuario_id = usuario_id
        self.novo_jogador_data = novo_jogador_data
        self.jogadores_existentes_data = {str(j.id): j for j in jogadores_existentes} # Mapeia ID para objeto JogadorUsuario

        options = []
        for j in jogadores_existentes:
            options.append(discord.SelectOption(
                label=f"{j.nome} (Habilidade: {j.habilidade}, Posição: {j.posicao}{' - Titular' if j.titular else ''})",
                value=str(j.id) # Usar o ID do jogador como valor
            ))

        self.add_item(discord.ui.Select(
            placeholder="Selecione um jogador para substituir...",
            options=options,
            min_values=1,
            max_values=1,
            custom_id="select_substituir_elenco"
        ))

    async def interaction_check(self, interaction: discord.Interaction):
        return interaction.user.id == self.usuario_id

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.grey, custom_id="cancelar_substituicao_elenco")
    async def cancelar_substituicao(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("❌ Substituição cancelada. O novo jogador não foi adicionado.", ephemeral=True)
        self.stop() # Encerra a view

    @discord.ui.select(custom_id="select_substituir_elenco")
    async def select_jogador_substituir_elenco(self, interaction: discord.Interaction, select: discord.ui.Select):
        session = Session()
        try:
            jogador_id_para_substituir = int(select.values[0])
            jogador_a_remover = session.query(JogadorUsuario).filter_by(
                id=jogador_id_para_substituir,
                usuario_id=session.query(Usuario).filter_by(discord_id=str(interaction.user.id)).first().id
            ).first()

            if jogador_a_remover:
                # Remove o jogador antigo
                session.delete(jogador_a_remover)

                # Adiciona o novo jogador
                novo_jogador = JogadorUsuario(
                    nome=self.novo_jogador_data['nome'],
                    posicao=self.novo_jogador_data['posicao'],
                    habilidade=self.novo_jogador_data['habilidade'],
                    preco=self.novo_jogador_data['preco'],
                    titular=None, # O novo jogador entra como reserva
                    usuario_id=session.query(Usuario).filter_by(discord_id=str(interaction.user.id)).first().id
                )
                session.add(novo_jogador)
                session.commit()

                await interaction.response.send_message(
                    f"✅ **{self.novo_jogador_data['nome']}** substituiu **{jogador_a_remover.nome}** no seu elenco!",
                    ephemeral=False
                )
                self.stop() # Encerra a view
            else:
                await interaction.response.send_message("❌ Erro: Jogador a ser substituído não encontrado.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Ocorreu um erro ao processar a substituição: {e}", ephemeral=True)
            print(f"Erro na substituição de elenco: {e}")
        finally:
            session.close()

# --- Nova View para Substituição de Jogadores Titulares (Botão 'Promover') ---
class SubstituirTitularSelect(discord.ui.Select):
    def __init__(self, jogador_sendo_promovido_id, opcoes_substituicao, usuario_id):
        super().__init__(placeholder="Selecione qual titular substituir...", min_values=1, max_values=1, options=opcoes_substituicao)
        self.jogador_sendo_promovido_id = jogador_sendo_promovido_id
        self.usuario_id = usuario_id

    async def callback(self, interaction: discord.Interaction):
        session = Session()
        try:
            jogador_titular_id_para_remover = int(self.values[0])

            # Encontra o jogador titular a ser removido da posição
            jogador_titular_a_despromover = session.query(JogadorUsuario).filter_by(
                id=jogador_titular_id_para_remover,
                usuario_id=session.query(Usuario).filter_by(discord_id=str(interaction.user.id)).first().id
            ).first()

            # Encontra o jogador que será promovido
            jogador_a_promover = session.query(JogadorUsuario).filter_by(
                id=self.jogador_sendo_promovido_id,
                usuario_id=session.query(Usuario).filter_by(discord_id=str(interaction.user.id)).first().id
            ).first()

            if jogador_titular_a_despromover and jogador_a_promover:
                posicao_ocupada = jogador_titular_a_despromover.titular
                jogador_titular_a_despromover.titular = None # Despromove o jogador
                jogador_a_promover.titular = posicao_ocupada # Promove o novo jogador para a posição vaga

                session.commit()

                embed = discord.Embed(
                    title="SUBSTITUIÇÃO DE TITULAR!",
                    description=(
                        f"**{jogador_a_promover.nome}** é o novo {posicao_ocupada} do seu time!\n"
                        f"**{jogador_titular_a_despromover.nome}** agora é reserva."
                    ),
                    color=discord.Color.blue()
                )
                await interaction.response.send_message(embed=embed, ephemeral=False)
            else:
                await interaction.response.send_message("❌ Erro: Não foi possível encontrar os jogadores para a troca de titular.", ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(f"Ocorreu um erro ao processar a promoção: {e}", ephemeral=True)
            print(f"Erro na promoção de titular: {e}")
        finally:
            session.close()


async def setup(bot):
    await bot.add_cog(Dream(bot))