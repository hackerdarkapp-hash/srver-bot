"""
tools/legal_info.py — المعلومات القانونية وروابط الدعم الرسمي
"""


def get_legal_info(topic: str = "main") -> str:
    topics = {
        "main": _main_menu(),
        "report": _report_accounts(),
        "protect": _protect_account(),
        "privacy": _privacy_policies(),
        "support": _support_links(),
    }
    return topics.get(topic, _main_menu())


def _main_menu() -> str:
    return (
        "⚖️ <b>المعلومات القانونية والأمنية</b>\n"
        f"{'━' * 22}\n\n"
        "اختر الموضوع الذي تريد معرفته:\n\n"
        "📢 <b>الإبلاغ عن حسابات</b> — كيفية الإبلاغ في كل منصة\n"
        "🔒 <b>حماية حسابك</b> — خطوات عملية للحماية\n"
        "📋 <b>سياسات الخصوصية</b> — روابط سياسات المنصات\n"
        "🆘 <b>روابط الدعم الرسمي</b> — مراكز المساعدة\n\n"
        "اضغط على الموضوع 👇"
    )


def _report_accounts() -> str:
    return (
        "📢 <b>كيفية الإبلاغ عن حسابات مسيئة</b>\n"
        f"{'━' * 22}\n\n"
        "🔷 <b>Instagram:</b>\n"
        "  اضغط على النقاط (⋯) → الإبلاغ → اتبع الخطوات\n"
        "  🔗 instagram.com/help\n\n"
        "🔷 <b>Facebook:</b>\n"
        "  اضغط على (···) في الملف الشخصي → الإبلاغ\n"
        "  🔗 facebook.com/help\n\n"
        "🔷 <b>X (Twitter):</b>\n"
        "  اضغط (...) → الإبلاغ عن التغريدة أو الحساب\n"
        "  🔗 help.twitter.com\n\n"
        "🔷 <b>TikTok:</b>\n"
        "  اضغط على السهم → الإبلاغ → حدد السبب\n"
        "  🔗 support.tiktok.com\n\n"
        "🔷 <b>Telegram:</b>\n"
        "  @spambot — للإبلاغ عن السبام\n"
        "  🔗 t.me/spambot\n\n"
        "⚠️ <i>الإبلاغ يجب أن يكون لأسباب مشروعة وحقيقية فقط.</i>"
    )


def _protect_account() -> str:
    return (
        "🔒 <b>كيفية حماية حسابك</b>\n"
        f"{'━' * 22}\n\n"
        "✅ <b>خطوات أساسية:</b>\n"
        "  1️⃣ فعّل التحقق بخطوتين (2FA) في كل حساباتك\n"
        "  2️⃣ استخدم كلمة مرور فريدة لكل موقع\n"
        "  3️⃣ لا تستخدم شبكات WiFi عامة بدون VPN موثوق\n"
        "  4️⃣ لا تضغط على روابط مجهولة المصدر\n"
        "  5️⃣ راجع الجلسات النشطة دورياً وأغلق غير المعروفة\n\n"
        "🔐 <b>للحسابات الحساسة:</b>\n"
        "  ✓ استخدم بريداً مخصصاً لكل خدمة\n"
        "  ✓ لا تربط حسابات بحسابات أخرى دون ضرورة\n"
        "  ✓ استخدم مفتاح أمان مادي (Hardware Key) إن أمكن\n"
        "  ✓ تحقق من صلاحيات التطبيقات المرتبطة بحسابك\n\n"
        "📱 <b>للهاتف:</b>\n"
        "  ✓ حدّث التطبيقات والنظام دائماً\n"
        "  ✓ لا تحمّل تطبيقات من مصادر غير رسمية\n"
        "  ✓ استخدم قفل الشاشة وقفل التطبيقات الحساسة"
    )


def _privacy_policies() -> str:
    return (
        "📋 <b>سياسات الخصوصية الرسمية</b>\n"
        f"{'━' * 22}\n\n"
        "🔷 <b>Telegram:</b>\n"
        "  telegram.org/privacy\n\n"
        "🔷 <b>Instagram / Meta:</b>\n"
        "  privacycenter.instagram.com\n\n"
        "🔷 <b>Facebook / Meta:</b>\n"
        "  facebook.com/privacy/policy\n\n"
        "🔷 <b>X (Twitter):</b>\n"
        "  twitter.com/en/privacy\n\n"
        "🔷 <b>TikTok:</b>\n"
        "  tiktok.com/legal/privacy-policy\n\n"
        "🔷 <b>Google:</b>\n"
        "  policies.google.com/privacy\n\n"
        "🔷 <b>Apple:</b>\n"
        "  apple.com/privacy\n\n"
        "⚠️ <i>اقرأ سياسات الخصوصية قبل الموافقة على أي خدمة.</i>"
    )


def _support_links() -> str:
    return (
        "🆘 <b>مراكز الدعم الرسمي</b>\n"
        f"{'━' * 22}\n\n"
        "🔷 <b>Telegram:</b>\n"
        "  @TelegramSupport أو telegram.org/support\n\n"
        "🔷 <b>Instagram:</b>\n"
        "  help.instagram.com\n\n"
        "🔷 <b>Facebook:</b>\n"
        "  facebook.com/help\n\n"
        "🔷 <b>X (Twitter):</b>\n"
        "  help.twitter.com\n\n"
        "🔷 <b>TikTok:</b>\n"
        "  support.tiktok.com\n\n"
        "🔷 <b>GitHub:</b>\n"
        "  support.github.com\n\n"
        "🔷 <b>Google Account:</b>\n"
        "  support.google.com\n\n"
        "⚠️ <i>تواصل دائماً مع الدعم الرسمي فقط — لا تثق بأي روابط أخرى.</i>"
    )
