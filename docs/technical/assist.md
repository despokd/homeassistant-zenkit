# Assist shopping list

Issue #16. Sentences like "add milk to my shopping list" match two built-in intents of [home-assistant/intents](https://github.com/home-assistant/intents):

- `HassShoppingListAddItem` / `HassShoppingListCompleteItem` (domain `shopping_list`): no list name, "add {item} to [my|the] [shopping] list".
- `HassListAddItem` / `HassListCompleteItem` / `HassListRemoveItem` (domain `todo`): need the list name, "add {item} to [my|the] {name} [list]".

The default conversation agent loads the sentences of all built-in intents, whether or not a handler is registered (`_load_intents` in `conversation/default_agent.py`). Of the matches, hassil's `recognize_best` prefers custom sentences, then a match with a real `name` entity, then the most literal text. So the Shopping List intent wins unless an exposed todo entity's name is in the sentence. Without the Shopping List integration set up, handling fails; the issue reports the same with its entry disabled.

Shopping List is the only built-in "default list": all other list intents need a name.

## Sentence triggers

Sentence triggers (the conversation automation trigger) are matched before any intent (`async_recognize_sentence_trigger`). `assist.py` registers the Shopping List sentences as triggers with `get_agent_manager(hass).register_trigger(sentences, callback)` when a list is chosen in the options (`CONF_SHOPPING_LIST`, the list uuid). The callback returns the spoken answer; the triggers are removed on unload, and the options flow reloads the entry.

- `get_agent_manager` is not in the public `__all__` of `conversation`, but its `register_trigger` is what the conversation trigger platform uses. `helpers.trigger.async_initialize_triggers` with a `conversation` trigger would be public, but answers only through a `ScriptRunResult`.
- The callback calls the `todo.get_items`, `todo.add_item` and `todo.update_item` actions on the entity found by unique id (`<entry_id>_<list uuid>`), so it writes like the UI does and survives renamed entity ids.
- Sentences are registered in the language of Home Assistant (`hass.config.language`), English for languages without sentences. The trigger intents are compiled in that language too.
- A trigger can't decline a match: a matched trigger always answers. The upstream German sentences make the preposition before the list optional, so the `{item}` wildcard could take "Putzen zur Haushalts" from "füge Putzen zur Haushaltsliste hinzu". The sentences here require the preposition right after `{item}`; `tests/test_assist.py` checks the named list sentences of `HassListAddItem` and co. don't match.
- `hassil`, `home-assistant-intents` and `gazetteer-matcher` (requirements of `conversation`) are test requirements.
