// Loaded only by the modified private editor bundle. No system-wide injection.
// Qt QObject ABI was checked against this build's exported QObject vtable:
// metaObject, qt_metacast, qt_metacall, destructor, deleting destructor.
#include <cstdio>
#include <cstring>
#include <cctype>
#include <mutex>
#include <string>
#include <unordered_set>
#include <unistd.h>
#import <AppKit/AppKit.h>
#import <objc/runtime.h>

extern "C" bool vendor_support(const char*) asm("__ZN3krt4kcmc7supportEPKc");
extern "C" const char* qt_class_name(const void*) asm("__ZNK6kso_qt11QMetaObject9classNameEv");
extern "C" void qt_set_visible(void*, bool) asm("__ZN6kso_qt7QWidget10setVisibleEb");
extern "C" void qt_set_opacity(void*, double) asm("__ZN6kso_qt7QWidget16setWindowOpacityEd");
extern "C" void qt_show(void*) asm("__ZN6kso_qt7QWidget4showEv");
extern "C" int qt_dialog_exec(void*) asm("__ZN6kso_qt7QDialog4execEv");
extern "C" int qt_index_of_slot(const void*, const char*) asm("__ZNK6kso_qt11QMetaObject11indexOfSlotEPKc");
extern "C" void qt_single_shot(int, const void*, const char*) asm("__ZN6kso_qt6QTimer10singleShotEiPKNS_7QObjectEPKc");

#ifndef HAIHOME_AUDIT_PATH
#define HAIHOME_AUDIT_PATH "/dev/null"
#endif

static void record(const char* kind, const char* name, bool suppressed) {
    if (!name) return;
    static auto* seen = new std::unordered_set<std::string>;
    static auto* lock = new std::mutex;
    std::lock_guard<std::mutex> guard(*lock);
    std::string key = std::string(kind) + " " + name;
    if (seen->size() >= 12000 || !seen->insert(key).second) return;
    if (FILE* log = fopen(HAIHOME_AUDIT_PATH, "a")) {
        fprintf(log, "%d\t%s\t%s\t%s\n", getpid(), kind,
                suppressed ? "suppressed" : "unchanged", name);
        fclose(log);
    }
}

static bool vendor_cloud_text(NSString* title) {
    return [title containsString:@"保存至云文档"] || [title containsString:@"保存到云文档"] ||
        [title containsString:@"备份到云"] || [title containsString:@"文档不怕丢"] ||
        [title localizedCaseInsensitiveContainsString:@"Save to Cloud"] ||
        [title localizedCaseInsensitiveContainsString:@"Backup to Cloud"];
}
static bool contains_cloud_promotion(NSView* view) {
    if ([view isKindOfClass:[NSButton class]] && vendor_cloud_text([(NSButton*)view title])) return true;
    if ([view isKindOfClass:[NSTextField class]] && vendor_cloud_text([(NSTextField*)view stringValue])) return true;
    NSString* cls = NSStringFromClass([view class]);
    if ([cls localizedCaseInsensitiveContainsString:@"cloud"] ||
        [cls localizedCaseInsensitiveContainsString:@"roaming"]) return true;
    for (NSView* child in [view subviews]) if (contains_cloud_promotion(child)) return true;
    return false;
}
static bool contains_format_selector(NSView* view) {
    if ([view isKindOfClass:[NSPopUpButton class]]) return true;
    for (NSView* child in [view subviews]) if (contains_format_selector(child)) return true;
    return false;
}
static void strip_cloud_buttons(NSView* view) {
    for (NSView* child in [[view subviews] copy]) {
        // This version adds an unlabeled info button next to the cloud-backup
        // promotion. It is inside the accessory view, not the system panel.
        // Keep the named encryption button and the format popup.
        bool orphan_info = [child isKindOfClass:[NSButton class]] &&
            ![child isKindOfClass:[NSPopUpButton class]] &&
            [[(NSButton*)child title] length] == 0 && [[child toolTip] length] == 0;
        if (orphan_info || (contains_cloud_promotion(child) && !contains_format_selector(child))) {
            record("native-accessory", [NSStringFromClass([child class]) UTF8String], true);
            [child removeFromSuperview];
        }
        else strip_cloud_buttons(child);
    }
}
static void (*original_accessory)(id, SEL, NSView*);
static void local_accessory(id panel, SEL selector, NSView* view) {
    strip_cloud_buttons(view);
    original_accessory(panel, selector, view);
}
static void (*original_button_title)(id, SEL, NSString*);
static void local_button_title(id button, SEL selector, NSString* title) {
    original_button_title(button, selector, title);
    // WPS adds this native button to the macOS save panel accessory view.
    // Retain the format selector and standard Save/Cancel buttons.
    if (vendor_cloud_text(title)) {
        [(NSButton*)button setHidden:YES];
        [(NSButton*)button setEnabled:NO];
        [(NSButton*)button setTarget:nil];
        [(NSButton*)button setAction:nullptr];
        [(NSButton*)button removeFromSuperview];
        record("native-button", "save-to-vendor-cloud", true);
    }
}

__attribute__((constructor)) static void install_native_policy() {
    Method method = class_getInstanceMethod([NSButton class], @selector(setTitle:));
    if (method) {
        original_button_title = reinterpret_cast<decltype(original_button_title)>(method_getImplementation(method));
        class_replaceMethod([NSButton class], @selector(setTitle:),
            reinterpret_cast<IMP>(local_button_title), method_getTypeEncoding(method));
    }
    method = class_getInstanceMethod([NSSavePanel class], @selector(setAccessoryView:));
    if (method) {
        original_accessory = reinterpret_cast<decltype(original_accessory)>(method_getImplementation(method));
        class_replaceMethod([NSSavePanel class], @selector(setAccessoryView:),
            reinterpret_cast<IMP>(local_accessory), method_getTypeEncoding(method));
    }
}

static std::string lower(const char* name) {
    std::string s = name ? name : "";
    for (char& c : s) c = static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
    return s;
}

extern "C" bool haihome_support(const char* name) {
    const auto s = lower(name);
    bool off = s == "newhomepage" || s == "promedocertabbutton" ||
               s == "guidelogindialog" || s == "doceditinlogined" ||
               s == "enableloginentrancestyle" || s == "commonunloginbubble" ||
               s == "crossterminalbtn" || s == "coworkdockentrance" ||
               s == "lingxidockentrance" || s == "lingxidockentryvisible";
    for (const char* token : {"docer", "copilot", "aigc", "advertis", "promotion",
                              "forcelogin", "forcedlogin", "autologin", "loginwindow",
                              "loginpanel", "cloud", "startpage"})
        off = off || s.find(token) != std::string::npos;
    record("feature", name, off);
    // dyld's per-image interpose rules preserve this call to the original.
    return off ? false : vendor_support(name);
}

static const char* widget_class(void* object) {
    if (!object) return "";
    auto vtable = *reinterpret_cast<void***>(object);
    using Meta = const void* (*)(const void*);
    const void* meta = reinterpret_cast<Meta>(vtable[0])(object);
    return meta ? qt_class_name(meta) : "";
}

static bool optional_widget(const char* name) {
    return strstr(name, "DocerTab") || strstr(name, "HeaderAvatar") ||
           strstr(name, "Advertise") || strstr(name, "PremiumGuide") ||
           strstr(name, "GoPremium") || strstr(name, "MemberRemind") ||
           strstr(name, "Copilot") || strstr(name, "AIAccompany") ||
           strstr(name, "LoginGuide") || strstr(name, "CloudLogin") ||
           strstr(name, "DrTip") || strcmp(name, "UpgradeButtonGroup") == 0 ||
           strcmp(name, "KPromeCustomTabButton") == 0 ||
           strcmp(name, "KPromeFixedTabButton") == 0 ||
           strcmp(name, "KPromeTabWebIMEntryButton") == 0 ||
           strcmp(name, "KPromeNewTabButton") == 0 ||
           strcmp(name, "KNewLoginWin") == 0 ||
           strcmp(name, "KLoginWinSkeletonWidget") == 0;
}

extern "C" void haihome_show(void* object) {
    const char* name = widget_class(object);
    const bool off = optional_widget(name);
    record("widget-show", name, off);
    if (off) qt_set_visible(object, false);
    else qt_show(object);
}

extern "C" void haihome_set_visible(void* object, bool visible) {
    const char* name = widget_class(object);
    const bool off = visible && optional_widget(name);
    if (visible) record("widget", name, off);
    if (visible && strcmp(name, "KcfdFileDialog") == 0) qt_set_opacity(object, 0.0);
    qt_set_visible(object, off ? false : visible);
    if (visible && strcmp(name, "KcfdFileDialog") == 0) {
        auto table = *reinterpret_cast<void***>(object);
        using Meta = const void* (*)(const void*);
        const void* meta = reinterpret_cast<Meta>(table[0])(object);
        // Use the component's own native-Browse route. Queue the slot so its
        // existing modal loop owns the result and QObject lifetime is respected.
        if (qt_index_of_slot(meta, "onOpenMacFinderDlg()") >= 0) {
            // This slot preserves Open versus Save mode. The short delay allows
            // the original first-render callback to initialize format filters.
            qt_single_shot(500, object, "1onOpenMacFinderDlg()");
            record("native-save-route", "mac-finder-scheduled", false);
        } else record("native-save-route", "slot-missing", false);
    }
}

extern "C" int haihome_dialog_exec(void* object) {
    const char* name = widget_class(object);
    const bool off = strstr(name, "Login") || strstr(name, "login") || optional_widget(name);
    record("dialog", name, off);
    // Match the existing Cancel/Escape route; never fabricate logged-in state.
    return off ? 0 : qt_dialog_exec(object);
}

#define INTERPOSE(replacement, original, label) \
    __attribute__((used, section("__DATA,__interpose"))) \
    static const struct { const void* replacement; const void* original; } label = \
        { reinterpret_cast<const void*>(replacement), reinterpret_cast<const void*>(original) }

INTERPOSE(haihome_support, vendor_support, support_pair);
INTERPOSE(haihome_set_visible, qt_set_visible, visible_pair);
INTERPOSE(haihome_show, qt_show, show_pair);
INTERPOSE(haihome_dialog_exec, qt_dialog_exec, dialog_pair);
