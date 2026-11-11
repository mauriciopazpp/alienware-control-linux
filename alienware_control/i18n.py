"""Translations. Source strings are English; `_()` returns the active language's text.

To add a language: add its code to LANGUAGES and a dictionary to CATALOGS, keyed by the
English string. Missing entries fall back to English.
"""
import os

LANGUAGES = {"en": "English", "pt": "Português (Brasil)"}
current = "en"

PT = {
    # window / pages
    "Settings": "Configurações",
    "Dashboard": "Painel",
    "Lighting": "Luzes",
    "Power": "Energia",
    # dashboard
    "Right now": "Agora",
    "Disks": "Discos",
    "Battery": "Bateria",
    "Health": "Saúde",
    "no reading": "sem leitura",
    "hot": "quente",
    "warm": "morno",
    "normal": "normal",
    "active · ": "acordada · ",
    "sleeping · ": "dormindo · ",
    "CPU load": "Uso da CPU",
    "busy": "alto",
    "calm": "tranquilo",
    "Memory": "Memória",
    "of {size}": "de {size}",
    "tight": "cheia",
    "plenty free": "folgada",
    "stopped": "parada",
    "spinning": "girando",
    "CPU fan": "Ventoinha CPU",
    "GPU fan": "Ventoinha GPU",
    "charging": "carregando",
    "on battery": "descarregando",
    "plugged in, full": "na tomada, cheia",
    "plugged in, not charging": "na tomada, sem carregar",
    "{full} of {design} Wh when new. ": "{full} de {design} Wh de fábrica. ",
    "Worn: cap the charge level on the Power page.": "Desgastada: limite a carga na tela Energia.",
    "No mounted disks": "Sem discos montados",
    "Risk: a disk is {pct}% full": "Risco: um disco está em {pct}%",
    "Warning: a disk is {pct}% full": "Atenção: um disco está em {pct}%",
    "No disk at risk": "Discos sem risco",
    "{used} of {total} · {free} free": "{used} de {total} · {free} livres",
    "Risk": "Risco",
    "Warning": "Atenção",
    "OK": "OK",
    "{size} · not mounted": "{size} · não montado",
    "No reading": "Sem leitura",
    # lighting
    "VIEW": "VISTA",
    "Front": "Frente",
    "Back": "Traseira",
    "Click a light on the drawing to edit it": "Clique numa luz do desenho para editar",
    "Show the back": "Girar para a traseira",
    "Show the front": "Girar para a frente",
    "Keyboard": "Teclado",
    "Power button": "Botão",
    "Logo": "Logo",
    "Rear": "Traseira",
    "Scenes": "Cenas",
    "Neon": "Neon",
    "Ember": "Brasa",
    "Aurora": "Aurora",
    "Rainbow": "Arco-íris",
    "Ocean": "Oceano",
    "Focus": "Foco",
    "Lights off": "Apagar",
    "Colour 1": "Cor 1",
    "Colour 2": "Cor 2",
    "This effect has its own colours. Brightness still applies.":
        "Este efeito tem cores próprias. O brilho continua valendo.",
    "The power button LED has no blue: it shows red, green and their mixes (yellow, orange), and changes "
    "colour in steps.":
        "O LED do botão de ligar não tem azul: ele mostra vermelho, verde e as misturas (amarelo, laranja), "
        "e troca de cor em degraus.",
    "Blink": "Piscar",
    "Stars (typing)": "Estrelas (ao digitar)",
    "Ripple (typing)": "Gota (ao digitar)",
    "Colour stripes": "Faixas coloridas",
    "Traffic light": "Semáforo",
    "Effect": "Efeito",
    "hover to preview": "passe o mouse para ver",
    "Speed": "Velocidade",
    "Slow": "Lenta",
    "Normal": "Normal",
    "Fast": "Rápida",
    "Colour shift": "Troca de cor",
    "Spectrum": "Espectro",
    "Fire": "Fogo",
    "Sunset": "Pôr do sol",
    "Two halves": "Duas metades",
    "Swap": "Alternar",
    "Tide": "Maré",
    "Rainbow wave": "Onda arco-íris",
    "Police": "Polícia",
    "Brightness": "Brilho",
    "Quick colours": "Cores rápidas",
    "Keyboard effect": "Efeito do teclado",
    "Static": "Fixo",
    "Breathing": "Respirar",
    "Wave": "Onda",
    "Pulse": "Pulso",
    "Colour mix": "Mistura de cores",
    "Night rider": "Vai e volta",
    "Second colour": "Segunda cor",
    "Use this colour on all lights": "Usar esta cor em todas as luzes",
    "No Alienware lighting controller found: preview only.":
        "Nenhum controle de luz Alienware encontrado: só a prévia.",
    "Keyboard lighting controller not found on this computer.":
        "Controle de luz do teclado não encontrado neste computador.",
    "Power button / logo controller not found on this computer.":
        "Controle do botão e do logo não encontrado neste computador.",
    "off": "apagado",
    "Could not save the colours: {error}": "Não consegui salvar as cores: {error}",
    "Applying…": "Aplicando…",
    "Error: {error}": "Erro: {error}",
    "Applied to the laptop": "Aplicado no notebook",
    "Cyan": "Ciano",
    "Violet": "Violeta",
    "Red": "Vermelho",
    "Orange": "Laranja",
    "Green": "Verde",
    "Pink": "Rosa",
    "Blue": "Azul",
    "Cool white": "Branco frio",
    # power
    "Power profile": "Perfil de energia",
    "applies instantly, no password": "vale na hora, sem senha",
    "power-profiles-daemon is not installed": "power-profiles-daemon não está instalado",
    "Power saver": "Economia",
    "Low clocks, cooler and quieter": "Clock baixo, mais frio e silencioso",
    "Balanced": "Equilibrado",
    "Boosts only when needed": "Sobe o clock só quando precisa",
    "Performance": "Desempenho",
    "High clocks, more heat and fan noise": "Clock alto, mais calor e ventoinha",
    "Thermal mode": "Modo térmico",
    "Quiet": "Silencioso",
    "Less noise, limited power": "Menos ruído, potência limitada",
    "Recommended default": "Padrão recomendado",
    "Strong fans, for gaming": "Ventoinhas fortes, para jogos",
    "Saves power on battery": "Economia fora da tomada",
    "Turbo Boost": "Turbo Boost",
    "Turning it off runs much cooler, but the CPU is slower in bursts":
        "Desligar esfria muito, mas a CPU perde velocidade nos picos",
    "Battery charging": "Carga da bateria",
    "Mostly plugged in": "Uso na tomada",
    "Caps the charge level": "Limita a carga",
    "Adaptive": "Adaptativo",
    "The BIOS decides": "A BIOS decide",
    "Standard": "Padrão",
    "Full charge": "Carga completa",
    "Express": "Rápido",
    "Fast, wears the battery": "Rápido, desgasta mais",
    "Custom": "Personalizado",
    "You pick the range": "Você escolhe",
    "Start charging below (%)": "Começar a carregar abaixo de (%)",
    "Stop charging at (%)": "Parar de carregar em (%)",
    "Apply": "Aplicar",
    "Saved: {value}%": "Salvo: {value}%",
    "Thermal mode saved": "Modo térmico salvo",
    "Charging mode saved": "Modo de carga salvo",
    "Power profile: {name}": "Perfil de energia: {name}",
    "Could not change the power profile": "Não consegui trocar o perfil de energia",
    "BIOS settings are off: run the installer once": "Ajustes da BIOS desligados: rode o instalador uma vez",
    "How to install": "Como instalar",
    "Could not read the BIOS settings": "Não consegui ler a BIOS",
    "BIOS setting saved. Restart the computer to apply it.":
        "Ajuste da BIOS salvo. Reinicie o PC para aplicar.",
    "Turbo on": "Turbo ligado",
    "Turbo off": "Turbo desligado",
    "Cancelled: password not confirmed": "Cancelado: senha não confirmada",
    "Failed": "Falhou",
    "Install the helpers": "Instalar os ajudantes",
    "Open the project folder and double-click Install (or run: sudo installer/install.sh).\n\n"
    "Then open Alienware Control again.":
        "Abra a pasta do projeto e dê dois cliques em Install (ou rode: sudo installer/install.sh).\n\n"
        "Depois abra o Alienware Control de novo.",
    # settings
    "Theme": "Tema",
    "Applies to every page of the app": "Vale para todas as telas do app",
    "GTK (system)": "GTK (sistema)",
    "Follows your Linux theme": "Segue o tema do seu Linux",
    "Midnight blue, cyan and violet": "Azul-noite com ciano e violeta",
    "Pure black, cyan highlights": "Preto puro, brilhos em ciano",
    "Detected theme: {source}": "Tema detectado: {source}",
    "Language": "Idioma",
    "Automatic (system)": "Automático (sistema)",
    "General": "Geral",
    "Re-apply lighting at login": "Reaplicar as luzes no login",
    "Keyboard, power button and logo come back with your colours":
        "Teclado, botão e logo voltam com as suas cores",
    "Refresh the gauges every": "Atualizar os medidores a cada",
    "Temperature unit": "Temperatura em",
    "Disk space alert": "Alerta de disco cheio",
    "When the Linux disk fills up, apps can crash or lose data, updates can fail "
    "and the desktop may not start. Get a notification before that happens.":
        "Quando o disco do Linux enche, programas podem travar ou perder dados, atualizações "
        "podem falhar e a área de trabalho pode nem abrir. Receba um aviso antes disso.",
    "Warn when a Linux disk is almost full": "Avisar quando um disco Linux estiver quase cheio",
    "Checks every 10 minutes in the background, even with the app closed":
        "Confere a cada 10 minutos em segundo plano, mesmo com o app fechado",
    "Warn at": "Avisar em",
    "Percentage of the disk in use": "Porcentagem do disco em uso",
    "Send a test notification": "Enviar uma notificação de teste",
    "Test": "Testar",
    "No notification service found in this session": "Nenhum serviço de notificação nesta sessão",
    "About": "Sobre",
    "found": "detectado",
    "not found": "não detectado",
    "keyboard lighting: {state}": "luz do teclado: {state}",
    "power button/logo: {state}": "botão/logo: {state}",
    # theme detection
    "theme {name} not found": "tema {name} não encontrado",
    "{name} has no GTK 4 support": "{name} não tem suporte a GTK 4",
    "{name} (GTK 4 colours)": "{name} (cores do GTK 4)",
    "system default ({reason})": "padrão do sistema ({reason})",
    # disk notifications
    "The system disk is {pct}% full": "O disco do sistema está {pct}% cheio",
    "The disk at {mount} is {pct}% full": "O disco em {mount} está {pct}% cheio",
    "Only {free} left. When the Linux disk fills up, apps can crash or lose data, updates can fail "
    "and the desktop may not start. Free some space soon (Trash, Downloads, old Docker images, "
    "package caches).":
        "Restam só {free}. Quando o disco do Linux enche, programas podem travar ou perder dados, "
        "atualizações podem falhar e a área de trabalho pode nem abrir. Libere espaço logo "
        "(Lixeira, Downloads, imagens antigas do Docker, cache de pacotes).",
    "Computer": "Computador",
    # graphical installer
    "Install Alienware Control": "Instalar o Alienware Control",
    "Uninstall Alienware Control": "Desinstalar o Alienware Control",
    "Uninstall Alienware Control?": "Desinstalar o Alienware Control?",
    "This removes the app, its helpers and permissions. Your settings in ~/.config/alienware-control are kept.":
        "Isso remove o app, os ajudantes e as permissões. Suas configurações em "
        "~/.config/alienware-control são mantidas.",
    "Alienware Control is not installed on this computer.": "O Alienware Control não está instalado neste computador.",
    "Cancel": "Cancelar",
    "Temperatures, fans, disks, RGB lighting, thermal mode and battery charging for Alienware laptops on Linux.":
        "Temperaturas, ventoinhas, discos, luzes RGB, modo térmico e carga da bateria para notebooks "
        "Alienware no Linux.",
    "Tested only on an Alienware m15 R7. On other models some features may not work.":
        "Testado só num Alienware m15 R7. Em outros modelos, algumas funções podem não funcionar.",
    "Alienware Control is already installed.": "O Alienware Control já está instalado.",
    "Alienware Control is installed as a system package. Update or remove it from your software center or "
    "package manager.":
        "O Alienware Control está instalado como pacote do sistema. Atualize ou remova pela loja de "
        "aplicativos ou pelo gerenciador de pacotes.",
    "Uninstall": "Desinstalar",
    "Update": "Atualizar",
    "Next": "Avançar",
    "Back": "Voltar",
    "Install": "Instalar",
    "Close": "Fechar",
    "Your computer": "Seu computador",
    "What the installer found. Missing items only turn the matching feature off.":
        "O que o instalador encontrou. Um item que falta só desliga a função correspondente.",
    "GTK 4 and libadwaita 1.3+": "GTK 4 e libadwaita 1.3+",
    "Keyboard lighting": "Luz do teclado",
    "Power button and logo lighting": "Luz do botão e do logo",
    "BIOS settings (Dell WMI)": "Ajustes da BIOS (Dell WMI)",
    "Power profiles": "Perfis de energia",
    "Password prompt (polkit)": "Pedido de senha (polkit)",
    "NVIDIA GPU": "GPU NVIDIA",
    "libadwaita 1.3 or newer is required. Update your system first, then run the installer again.":
        "É preciso o libadwaita 1.3 ou mais novo. Atualize o sistema e rode o instalador de novo.",
    "Options": "Opções",
    "You can run the installer again later to change them.": "Dá para rodar o instalador de novo depois para mudar.",
    "Let the NVIDIA GPU sleep when idle": "Deixar a GPU NVIDIA dormir quando estiver parada",
    "Saves 10 to 15 W and keeps the GPU fan quiet on some laptops":
        "Economiza de 10 a 15 W e deixa a ventoinha da GPU quieta em alguns notebooks",
    "Files go to /usr/local, plus a polkit policy and a udev rule. You will be asked for your password once.":
        "Os arquivos vão para /usr/local, mais uma regra do polkit e uma do udev. A senha é pedida uma vez.",
    "Installing…": "Instalando…",
    "Uninstalling…": "Desinstalando…",
    "Follow the password prompt if one appears.": "Se aparecer o pedido de senha, digite a sua.",
    "The password was not confirmed, so nothing was changed.": "A senha não foi confirmada, então nada mudou.",
    "All set": "Pronto",
    "Alienware Control is installed. You can find it in your app menu.":
        "O Alienware Control está instalado. Ele aparece no menu de aplicativos.",
    "Open Alienware Control": "Abrir o Alienware Control",
    "Removed": "Removido",
    "Alienware Control was uninstalled. Your settings were kept.":
        "O Alienware Control foi desinstalado. Suas configurações foram mantidas.",
    "Something went wrong": "Algo deu errado",
    "See the details on the previous screen.": "Veja os detalhes na tela anterior.",
    "Show details": "Ver detalhes",
}

CATALOGS = {"pt": PT}


def system_language():
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(var, "")
        for part in value.split(":"):
            code = part.split("_")[0].split(".")[0].lower()
            if code in LANGUAGES:
                return code
    return "en"


def setup(choice):
    """choice: 'auto' or a code from LANGUAGES."""
    global current
    current = system_language() if choice == "auto" else (choice if choice in LANGUAGES else "en")
    return current


def _(text):
    catalog = CATALOGS.get(current)
    return catalog.get(text, text) if catalog else text
