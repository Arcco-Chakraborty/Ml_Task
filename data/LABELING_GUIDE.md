# Dataset & labelling guide

## Files

| File | What |
|---|---|
| `train.csv` | 1,126 labelled user messages: `id, text, label, duplicate_of` |
| `suggestions.json` | The suggestions board as it is today: `id, text, count` (32 entries) |
| `known_issues.json` | Known bugs: `id, title, status (open/fixed), fixed_in, component` (24 entries) |

This is real-looking user feedback, so expect mess: half-formed sentences ("umm the hourly thing is like... empty?"),
keyboard mash, autocorrect fails ("the raider is blanket" = the radar is blank), typos, SMS-speak ("u", "pls", "y"),
ALL CAPS, missing punctuation, emojis, greetings and sign-offs ("Dear Sir/Madam", "- sent from
my phone"), pasted error messages, Hinglish ("bhai", "kaise", "nahi"), and some Hindi or Punjabi
in their own scripts.

**The labels were made by human annotators, and a small number of them are wrong.** That's normal
for real data. Finding and handling them is part of the job (and a good thing to talk about in
your report).

The hidden test set (about 360 messages) is written in the same style but with **different
wording**, and it is noticeably messier than `train.csv`. Don't overfit to exact phrases.

## Labels

Every message gets exactly one label.

| Label | Meaning |
|---|---|
| `query` | Asks how something works, what something means, or whether a feature exists. |
| `suggestion` | Asks for something the app **doesn't have**: a new feature or a change in design. |
| `bug` | Says something the app **does have** is broken, crashes, or shows clearly wrong data. |
| `junk` | Nothing to act on: keyboard mash, "test", bare greetings or thanks, "nvm", spam and forwards, off-topic questions, praise or abuse with no content, a bare feature name, chatter about the weather itself. |

**Go by intent, not wording.** Users don't phrase things the way the label says.

| Message | Label | Why |
|---|---|---|
| "Why is the radar not showing anything?" | bug | question form, but it reports a malfunction |
| "please make the widget actually update, that's all I ask" | bug | reads like a request, but the widget exists and is broken |
| "the app doesn't have a dark mode. at all." | suggestion | reads like a complaint, but dark mode was never built |
| "the forecast just stops after 7 days, really limiting" | suggestion | that's by design (and it's S32 on the board) |
| "is the radar issue fixed in the latest version?" | bug | asking about the status of a malfunction |
| "any plans to add pollen data?" | suggestion | asking for a feature to be added |
| "Can I see pollen levels in the app?" | query | asking whether a feature exists |
| "can you please tell me how to add a widget" | query | polite wording, but it's a how-to |
| "is it normal that the radar only updates every 10 minutes?" | query | asks whether behaviour is expected; claims nothing is broken |
| "wow 2026 and still no dark mode. incredible." | suggestion | sarcasm is still a feature request |
| "raining here in pune 🌧️" | junk | about the weather, not about the app |
| "nice app 👍" | junk | praise with nothing to act on |
| "radar" | junk | a bare feature name: we can't tell what they want |
| "pls fix" | bug | clearly reporting a malfunction, even if we can't tell which (no duplicate) |
| "add cover menu cant click" | bug | garbled ("ad covers the menu"), but the intent is recoverable: B18 |
| "barish ho rhi h app bol rha 0%" | bug | Hinglish: "it's raining and the app says 0%": B12 |

### Rules

1. **Exists but misbehaves → bug.** Even when phrased as a wish ("would be nice if X worked"), a suggestion ("feature request: a feels-like that's actually different") or a question.
2. **Doesn't exist → suggestion.** Even when phrased as a complaint or a defect ("X is missing", "can't find X anywhere", "there's no X").
3. **"Is X fixed yet?" about a malfunction → bug** (link it to the known issue).
4. **"Any plans to / will you ever add X?" → suggestion.** "Is there X?" / "Does the app have X?" → query.
5. **Explaining or checking behaviour → query.** "Why is feels-like lower than the temperature today?" or "is that normal?" is a query; "Feels like is always exactly the same as the actual temperature" is a bug.
6. **Mixed messages: bug > suggestion > query.** Praise or a long story around it doesn't matter; neither does a request tacked on the end. The duplicate annotation follows the chosen label.
7. Politeness, praise, sarcasm, emojis, typos, language and third person ("my mom says it crashes") don't change the label.
8. **Junk only when there's genuinely nothing to act on.** If you can work out the intent through the garbling, use the real label. A bare complaint ("not working", "pls fix") is a bug; a greeting, "test", "nvm" or "ok thanks" is junk.

How do you know whether a feature exists? From the app itself (run it), from the suggestions board
(everything on it is something the app doesn't have yet), and from the training data.

## Duplicates

`duplicate_of` is filled in for **suggestion** and **bug** messages only (never for query or junk):

- `S07` etc.: the message asks for the same thing as that entry in `suggestions.json`
- `B12` etc.: the message reports the same problem as that entry in `known_issues.json`
- empty: it's something new

**Same topic is not the same request.** The lists contain deliberately similar entries:

| Entries | Difference |
|---|---|
| B02 widget doesn't refresh · B21 widget shows the wrong city · B05 app detects the wrong city | stale ≠ wrong city; widget ≠ app |
| B06 alerts never arrive · B22 same alert arrives many times | none ≠ too many |
| B04 radar blank · B23 radar animation choppy | nothing shown ≠ shown badly |
| S02 lock screen widget · S30 more home-screen widget sizes | lock screen ≠ home screen |
| S06 notify before rain starts · S29 notify when rain stops | start ≠ stop |
| S08 AQI pollutant breakdown · S31 AQI alerts · S20 UV alerts | breakdown ≠ alert; AQI ≠ UV |
| S04 48-hour hourly forecast · S32 14-15 day daily forecast | hourly ≠ daily |

And some messages match **nothing** even though they look close, for example:
"Show minute-by-minute rain for the next hour as a graph" (a graph, not S06's notification), or
"Celsius selected but the widget shows Fahrenheit" (a widget display bug, not B03's setting that
isn't saved).

Wording can also be very different and still be a duplicate:
"Would love a moon calendar, I do astrophotography" **is** S10 (moon phases).

### New suggestions during a run

When a suggestion matches nothing, the app adds it to the board. A later message asking for the
same new thing should match **that** new entry. Your `match_suggestion` always receives the
current list, including entries added at runtime, so this works without special handling, as long
as you match against what you're given rather than a list frozen at training time.
