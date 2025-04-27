from config import APP_VERSION, COMMAND_PREFIX, Config


class AlbertMsg:
    common_msg_prefixes = [
        "👋 Bonjour, je suis **Albert**",
        "🤖 Configuration actuelle",
        "\u26a0\ufe0f **Erreur**",
        "\u26a0\ufe0f **Commande inconnue**",
        "**La conversation a été remise à zéro**",
        "🤖 Albert a échoué",
    ]
    shorts = {
        "help": f"Pour retrouver ce message informatif, tapez `{COMMAND_PREFIX}aide`. Pour les geek tapez `{COMMAND_PREFIX}aide -v`.",
        "reset": f"Pour ré-initialiser notre conversation, tapez `{COMMAND_PREFIX}reset`",
        "collections": f"Pour modifier l'ensemble des collections utilisées quand vous me posez une question, tapez `{COMMAND_PREFIX}collections list/use/unuse/info COLLECTION_NAME`",
        "conversation": f"Pour activer/désactiver le mode conversation, tapez `{COMMAND_PREFIX}conversation`",
        "debug": f"Pour afficher des informations sur la configuration actuelle, `{COMMAND_PREFIX}debug`",
        "model": f"Pour modifier le modèle, tapez `{COMMAND_PREFIX}model MODEL_NAME`",
        "mode": f"Pour modifier le mode du modèle (c'est-à-dire le modèle de prompt utilisé), tapez `{COMMAND_PREFIX}mode MODE`",
        "sources": f"Pour obtenir les sources utilisées pour générer ma dernière réponse, tapez `{COMMAND_PREFIX}sources`",
    }

    failed = "🤖 Albert a échoué à répondre. Veuillez réessayez dans un moment."

    flush_start = "Nettoyage des collections RAG propres à cette conversation..."

    flush_end = "Nettoyage des collections RAG terminé."

    reset = "**La conversation a été remise à zéro**. Vous pouvez néanmoins toujours répondre dans un fil de discussion."

    user_not_allowed = "Albert est en phase de test et n'est pas encore disponible pour votre utilisateur. Contactez albert-contact@data.gouv.fr pour demander un accès."

    domain_not_allowed = "Albert n'est pas encore disponible pour votre domaine. Merci de rester en contact, il sera disponible après une phase beta test."

    def error_debug(reason, config):
        api_url = getattr(config, 'albert_api_url', 'N/A')
        msg = f"\u26a0\ufe0f **Erreur**\n\n{reason}\n\n- Serveur Matrix: {config.matrix_home_server}"
        if api_url != 'N/A':
            msg = f"\u26a0\ufe0f **Albert API error**\n\n{reason}\n\n- Albert API URL: {api_url}\n- Matrix server: {config.matrix_home_server}"
        return msg

    def help(model_url, model_short_name, cmds):
        msg = "👋 Bonjour, je suis **Albert**, votre **assistant automatique dédié aux questions légales et administratives** mis à disposition par la **DINUM**. Je suis actuellement en phase de **test**.\n\n"
        msg += f"J'utilise le modèle de langage _[{model_short_name}]({model_url})_ et j'ai été alimenté par des bases de connaissances gouvernementales, comme les fiches pratiques de service-public.fr éditées par la Direction de l'information légale et administrative (DILA).\n\n"
        msg += "Maintenant que nous avons fait plus connaissance, quelques **règles pour m'utiliser** :\n\n"
        msg += "✅ Vous pouvez m'attacher en pièces jointes des documents pdf qui m'aideront à répondre plus efficacement.\n\n"
        msg += "🔮 Ne m'utilisez pas pour élaborer une décision administrative individuelle.\n\n"
        msg += "❌ **Ne me transmettez pas** :\n"
        msg += "- des fichiers autres que pdf, ni des images;\n"
        msg += "- des données permettant de **vous** identifier ou **d'autres personnes** ;\n"
        msg += "- des données **confidentielles** ;\n\n"
        msg += "Enfin, quelques informations pratiques :\n\n"
        msg += "🛠️ **Pour gérer notre conversation** :\n"
        msg += "- " + "\n- ".join(cmds)
        msg += "\n\n"
        msg += "📁 **Sur l'usage des données**\nLes conversations sont stockées de manière anonyme. Elles me permettent de contextualiser les conversations et l'équipe qui me développe les utilise pour m'évaluer et analyser mes performances.\n\n"
        msg += "📯 Nous contacter : albert-contact@data.gouv.fr"

        return msg

    def commands(cmds):
        msg = "Les commandes spéciales suivantes sont disponibles :\n\n"
        msg += "- " + "\n- ".join(cmds)  # type: ignore
        return msg

    def unknown_command(cmds_msg):
        msg = f"\u26a0\ufe0f **Commande inconnue**\n\n{cmds_msg}"
        return msg

    def reset_notif(delay_min):
        msg = f"Comme vous n'avez pas continué votre conversation avec Albert depuis plus de {delay_min} minutes, **la conversation a été automatiquement remise à zéro**. Vous pouvez néanmoins toujours répondre dans un fil de discussion.\n\n"
        msg += "Entrez **!aide** pour obtenir plus d'informatin sur ma paramétrisatiion."
        return msg

    def debug(config: Config):
        msg = "🤖 Configuration actuelle :\n\n"
        msg += f"- Version: {APP_VERSION}\n"
        
        # Vérifier si nous sommes en mode webhook ou Albert
        if hasattr(config, 'webhook_enabled') and config.webhook_enabled:
            msg += f"- Mode: Webhook\n"
            msg += f"- Webhook host: {config.webhook_host}\n"
            msg += f"- Webhook port: {config.webhook_port}\n"
        
        # Ajouter les infos Albert si disponibles
        api_url = getattr(config, 'albert_api_url', None)
        if api_url:
            msg += f"- API: {api_url}\n"
            msg += f"- Model: {getattr(config, 'albert_model', 'N/A')}\n"
            msg += f"- Mode: {getattr(config, 'albert_mode', 'N/A')}\n"
            msg += f"- With history: {getattr(config, 'albert_with_history', False)}\n"
        
        return msg
