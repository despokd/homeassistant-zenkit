---
name: todo-gaps
description: Update the gap list issue that compares this integration with Home Assistant to-do features, from new home-assistant/core pull requests.
disable-model-invocation: true
---

# Update the to-do gap list

The **gap list** is the GitHub issue "Gaps against Home Assistant to-do features" in `despokd/homeassistant-zenkit` (#73 when written). Its table maps home-assistant/core pull requests about to-do features to what this integration does today, and its sub-issues track the gaps worth implementing. The intro line ends with `Searched <date>`: the last run.

## Steps

### 1. Read the gap list

Find the issue by title, read its body, the `Searched` date and its sub-issues. Done when you hold the table rows, the date and the sub-issue numbers.

### 2. Find the labels

The to-do labels are `integration: todo` plus the label of every integration with a to-do platform. Start from the list in the intro line, then look for new ones: count the `integration: *` labels on to-do pull requests updated since the date, and keep the labels of integrations that have a to-do platform.

```bash
for q in 'todo in:title' 'to-do in:title' 'TodoListEntityFeature'; do
  gh api -X GET search/issues -f q="repo:home-assistant/core is:pr updated:>=DATE $q" \
    -f per_page=100 --paginate --jq '.items[] | .labels[].name'; sleep 4
done | grep '^integration:' | sort | uniq -c | sort -rn
```

Done when every label is either in the list or ruled out.

### 3. Search the pull requests

For each label, search pull requests updated since the date, open and closed. Search results carry each pull request's title, state, `merged_at` and body.

```bash
gh api -X GET search/issues -f q='repo:home-assistant/core is:pr label:"integration: todo" updated:>=DATE' \
  -f per_page=100 --paginate --jq '.items[] | "\(.number)\t\(.state)\t\(.pull_request.merged_at // "-")\t\(.title)"'
```

For an integration label, add `todo` to the query. Done when every label was searched.

### 4. Judge each pull request

Relevant are pull requests that add or change what a to-do entity can hold or do (item fields, `TodoListEntityFeature`, actions, intents, LLM tools) and integration-level patterns this integration could copy. Version bumps, refactors and test-only changes are noise.

For each relevant one, check this integration against it: `custom_components/zenkit/todo.py` (`_attr_supported_features`, `TodoItem` fields), `services.yaml`, `docs/technical/todoitem-mapping.md` and `docs/zenkit/`. Done when every relevant pull request is a new row, an update to a row (state changed, e.g. merged or closed), or listed under "Already in line with other integrations".

### 5. Update the gap list

Rewrite the issue body: table, "Already in line" list and `Searched <today>`.

- Write core references as `home-assistant/core#123`; a bare `#123` links to this repository.
- The "Issue" column holds this repository's issue number, or `—`.

### 6. Propose issues

For each new gap that works with what HA offers today, or tracks a bug in this integration, propose an issue to the user. On their yes: create it, link core pull requests as in step 5, add it as a sub-issue of the gap list (by the issue's `id`, not its number) and put its number in the table.

### 7. Report

List the new and changed rows, the issues created and the ones proposed but not created.
