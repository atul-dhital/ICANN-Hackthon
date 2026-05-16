"""Localized error messages for UAReady validator.

Provides clear, localised error strings as required by the problem statement.
Add more locales by extending MESSAGES.
"""

DEFAULT_LANG = "en"

MESSAGES = {
    "en": {
        "empty_input": "Input is empty.",
        "not_a_string": "Input must be a string.",
        "no_at_sign": "Email must contain exactly one '@'.",
        "multiple_at": "Email contains multiple '@' signs.",
        "empty_local": "Local part (before '@') is empty.",
        "empty_domain": "Domain part (after '@') is empty.",
        "local_too_long": "Local part exceeds 64 octets (RFC 5321 §4.5.3.1.1).",
        "email_too_long": "Email exceeds 254 octets total.",
        "local_invalid_chars": "Local part contains invalid characters for EAI / RFC 6532.",
        "local_dot_position": "Local part has leading, trailing, or consecutive dots.",
        "domain_too_long": "Domain exceeds 253 octets after IDNA encoding.",
        "label_too_long": "A domain label exceeds 63 octets.",
        "label_hyphen_position": "A domain label cannot start or end with a hyphen.",
        "domain_invalid_chars": "Domain contains forbidden characters under IDNA2008/UTS#46.",
        "domain_invalid_format": "Domain format is invalid under IDNA2008/UTS#46.",
        "idna_failed": "Domain failed IDNA2008/UTS#46 validation: {detail}",
        "domain_no_tld": "Domain should contain at least one dot (e.g. example.np).",
        "control_char": "Input contains control characters.",
        "mixed_scripts_local": "Local part mixes multiple scripts ({scripts}) — possible homograph risk (UTS #39).",
        "invalid_format": "Email failed RFC 6531/6532 validation: {detail}",
        "ok": "Valid.",
    },
    "ne": {
        "empty_input": "इनपुट खाली छ।",
        "not_a_string": "इनपुट स्ट्रिङ हुनुपर्छ।",
        "no_at_sign": "इमेलमा एउटा मात्र '@' चिन्ह हुनुपर्छ।",
        "multiple_at": "इमेलमा एक भन्दा बढी '@' छन्।",
        "empty_local": "'@' अघिको भाग खाली छ।",
        "empty_domain": "'@' पछिको डोमेन खाली छ।",
        "local_too_long": "स्थानीय भाग ६४ बाइट भन्दा बढी छ (RFC 5321)।",
        "email_too_long": "इमेल कुल २५४ बाइट भन्दा बढी छ।",
        "local_invalid_chars": "स्थानीय भागमा अमान्य अक्षर छ (RFC 6532)।",
        "local_dot_position": "स्थानीय भागमा सुरु/अन्त्य वा लगातार थोप्ला छन्।",
        "domain_too_long": "IDNA पछि डोमेन २५३ बाइट भन्दा बढी छ।",
        "label_too_long": "डोमेन लेबल ६३ बाइट भन्दा बढी छ।",
        "label_hyphen_position": "डोमेन लेबल हाइफनबाट सुरु वा अन्त्य हुन सक्दैन।",
        "domain_invalid_chars": "डोमेनमा IDNA2008/UTS#46 अनुसार निषेधित अक्षर छन्।",
        "domain_invalid_format": "डोमेनको ढाँचा IDNA2008/UTS#46 अनुसार अमान्य छ।",
        "idna_failed": "डोमेन IDNA2008/UTS#46 मा असफल: {detail}",
        "domain_no_tld": "डोमेनमा कम्तीमा एउटा थोप्लो हुनुपर्छ (जस्तै example.नेपाल)।",
        "control_char": "इनपुटमा नियन्त्रण अक्षर छन्।",
        "mixed_scripts_local": "स्थानीय भागमा विभिन्न लिपिहरू मिश्रित छन् ({scripts}) — सम्भावित होमोग्राफ जोखिम (UTS #39)।",
        "invalid_format": "इमेल RFC 6531/6532 परीक्षणमा असफल भयो: {detail}",
        "ok": "मान्य।",
    },
    "hi": {
        "empty_input": "इनपुट खाली है।",
        "not_a_string": "इनपुट स्ट्रिंग होना चाहिए।",
        "no_at_sign": "ईमेल में एक '@' चिह्न होना चाहिए।",
        "multiple_at": "ईमेल में एक से अधिक '@' हैं।",
        "empty_local": "'@' से पहले का भाग खाली है।",
        "empty_domain": "'@' के बाद का डोमेन खाली है।",
        "local_too_long": "स्थानीय भाग 64 बाइट से अधिक है।",
        "email_too_long": "ईमेल 254 बाइट से अधिक है।",
        "local_invalid_chars": "स्थानीय भाग में अमान्य वर्ण हैं।",
        "local_dot_position": "स्थानीय भाग में अमान्य डॉट स्थिति है।",
        "domain_too_long": "डोमेन 253 बाइट से अधिक है।",
        "label_too_long": "डोमेन लेबल 63 बाइट से अधिक है।",
        "label_hyphen_position": "डोमेन लेबल हाइफ़न से शुरू या समाप्त नहीं हो सकता।",
        "domain_invalid_chars": "डोमेन में IDNA2008/UTS#46 के अनुसार अमान्य वर्ण हैं।",
        "domain_invalid_format": "डोमेन का प्रारूप IDNA2008/UTS#46 के अनुसार अमान्य है।",
        "idna_failed": "डोमेन IDNA सत्यापन में विफल: {detail}",
        "domain_no_tld": "डोमेन में कम से कम एक डॉट होना चाहिए।",
        "control_char": "इनपुट में नियंत्रण वर्ण हैं।",
        "mixed_scripts_local": "स्थानीय भाग में विभिन्न लिपियाँ मिश्रित हैं ({scripts}) — संभावित होमोग्राफ जोखिम (UTS #39)।",
        "invalid_format": "ईमेल RFC 6531/6532 सत्यापन में विफल: {detail}",
        "ok": "मान्य।",
    },
    "ar": {
        "empty_input": "المدخل فارغ.",
        "not_a_string": "يجب أن يكون المدخل نصاً.",
        "no_at_sign": "يجب أن يحتوي البريد على علامة '@' واحدة.",
        "multiple_at": "البريد يحتوي على أكثر من علامة '@'.",
        "empty_local": "الجزء قبل '@' فارغ.",
        "empty_domain": "اسم النطاق بعد '@' فارغ.",
        "local_too_long": "الجزء المحلي يتجاوز 64 بايت.",
        "email_too_long": "البريد يتجاوز 254 بايت.",
        "local_invalid_chars": "الجزء المحلي يحتوي على أحرف غير صالحة.",
        "local_dot_position": "موضع النقطة غير صالح في الجزء المحلي.",
        "domain_too_long": "النطاق يتجاوز 253 بايت.",
        "label_too_long": "تسمية النطاق تتجاوز 63 بايت.",
        "label_hyphen_position": "لا يجوز أن تبدأ أو تنتهي تسمية النطاق بشرطة.",
        "domain_invalid_chars": "يحتوي النطاق على أحرف غير مسموح بها وفق IDNA2008/UTS#46.",
        "domain_invalid_format": "تنسيق النطاق غير صالح وفق IDNA2008/UTS#46.",
        "idna_failed": "فشل النطاق في تحقق IDNA2008/UTS#46: {detail}",
        "domain_no_tld": "يجب أن يحتوي النطاق على نقطة واحدة على الأقل.",
        "control_char": "المدخل يحتوي على أحرف تحكم.",
        "mixed_scripts_local": "الجزء المحلي يخلط نصوصاً متعددة ({scripts}) — خطر تشابه محتمل (UTS #39).",
        "invalid_format": "فشل البريد في تحقق RFC 6531/6532: {detail}",
        "ok": "صالح.",
    },
}


def msg(key, lang=DEFAULT_LANG, **kwargs):
    """Return a localized message; fall back to English if missing."""
    table = MESSAGES.get(lang) or MESSAGES[DEFAULT_LANG]
    template = table.get(key) or MESSAGES[DEFAULT_LANG].get(key, key)
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError):
        return template
