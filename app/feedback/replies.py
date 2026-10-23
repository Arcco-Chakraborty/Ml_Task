"""Template replies shown to the user after they submit feedback."""


def build_reply(label, suggestion=None, created_new=False, issue=None, report_count=0):
    if label is None:
        return "Thanks for your feedback! We've received it and the team will take a look."

    if label == "junk":
        return ("Sorry, we couldn't quite understand that. Could you tell us a bit more? For example, "
                "what you were trying to do, or what went wrong.")

    if label == "query":
        return ("Thanks for your question! We've passed it on to our support team and "
                "someone will get back to you soon.")

    if label == "suggestion":
        if suggestion is None:
            return "Thanks for the suggestion! We've noted it for the product team."
        if created_new:
            return ("Thanks for the idea! It's new to us, so we've added it to our suggestions "
                    "board where others can back it too.")
        others = suggestion["count"] - 1
        people = "person has" if others == 1 else "people have"
        return (f"Great minds think alike: {others} other {people} asked for "
                f"\"{suggestion['text']}\". We've added your vote, which helps us prioritise it.")

    if label == "bug":
        if issue is None:
            return ("Sorry about that, and thanks for reporting it! It doesn't match any issue we "
                    "know about, so we've logged it for our engineers to investigate.")
        if issue["status"] == "fixed":
            version = f" in version {issue['fixed_in']}" if issue.get("fixed_in") else ""
            return (f"Thanks for reporting! This looks like a known issue (\"{issue['title']}\") "
                    f"that has already been fixed{version}. Please update to the latest version; "
                    "if it still happens after updating, let us know.")
        return (f"Thanks for reporting! This is a known issue (\"{issue['title']}\") and our team "
                f"is working on a fix. You're one of {report_count} people who reported it.")

    raise ValueError(f"unknown label {label!r}")
