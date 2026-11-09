// SPDX-License-Identifier: GPL-2.0-or-later
#include "effect/effect.h"
#include "effect/effecthandler.h"
#include "input.h"
#include "pointer_input.h"
#include "wayland/seat.h"
#include "wayland/surface.h"
#include "wayland_server.h"
#include "window.h"

#include <QDBusAbstractAdaptor>
#include <QDBusConnection>
#include <QDebug>
#include <QJsonDocument>
#include <QJsonObject>
#include <QPointer>
#include <QUuid>

namespace dotfiles::mouse {

class TargetEffect;

class TargetAdaptor final : public QDBusAbstractAdaptor {
    Q_OBJECT
    Q_CLASSINFO("D-Bus Interface", "org.tomjseery.MouseTarget")

public:
    explicit TargetAdaptor(TargetEffect* effect);

public Q_SLOTS:
    /// Return JSON describing the current pointer recipient, or the JSON null value.
    QString target();

private:
    TargetEffect* effect_;
};

class TargetEffect final : public KWin::Effect {
    Q_OBJECT

public:
    TargetEffect()
        : session_{QUuid::createUuid().toString(QUuid::WithoutBraces)} {
        new TargetAdaptor{this};
        auto bus{QDBusConnection::sessionBus()};
        object_registered_ = bus.registerObject(object_path, this, QDBusConnection::ExportAdaptors);
        if (!object_registered_) {
            qWarning() << "Mouse Target: could not register D-Bus object";
            return;
        }
        service_registered_ = bus.registerService(service_name);
        if (!service_registered_) {
            bus.unregisterObject(object_path);
            object_registered_ = false;
            qWarning() << "Mouse Target: could not acquire D-Bus service";
        }
    }

    ~TargetEffect() override {
        auto bus{QDBusConnection::sessionBus()};
        if (service_registered_)
            bus.unregisterService(service_name);
        if (object_registered_)
            bus.unregisterObject(object_path);
    }

    bool isActive() const override { return false; }

    QString snapshot() {
        const auto unknown{[this] {
            last_surface_.clear();
            surface_token_.clear();
            return QStringLiteral("null");
        }};
        auto* effects{KWin::effects};
        auto* input{KWin::input()};
        auto* server{KWin::waylandServer()};
        if (!effects || !input || !server || effects->isScreenLocked()
            || effects->hasActiveFullScreenEffect() || effects->isMouseInterception()
            || effects->hasKeyboardGrab() || input->isSelectingWindow())
            return unknown();

        auto* pointer{input->pointer()};
        auto* seat{server->seat()};
        if (!pointer || !seat || seat->isDrag() || pointer->isConstrained()
            || pointer->areButtonsPressed() || pointer->decoration())
            return unknown();
        auto* window{pointer->focus()};
        auto* surface{seat->focusedPointerSurface()};
        // Restrict this version to root application surfaces. Popups, subsurfaces,
        // compositor surfaces and decoration targets remain native.
        if (!window || !surface || pointer->hover() != window
            || window->isDeleted() || !window->isShown()
            || !window->isNormalWindow() || window->isInteractiveMove()
            || window->isInteractiveResize() || !surface->isMapped()
            || surface != window->surface() || window->resourceClass().isEmpty())
            return unknown();

        if (last_surface_.data() != surface) {
            last_surface_ = surface;
            surface_token_ = window->internalId().toString(QUuid::WithoutBraces)
                + QLatin1Char('/') + QUuid::createUuid().toString(QUuid::WithoutBraces);
        }
        const QJsonObject result{{QStringLiteral("session"), session_},
                                 {QStringLiteral("surface"), surface_token_},
                                 {QStringLiteral("app"), window->resourceClass()}};
        return QString::fromUtf8(QJsonDocument{result}.toJson(QJsonDocument::Compact));
    }

private:
    static constexpr auto service_name{"org.tomjseery.MouseTarget"};
    static constexpr auto object_path{"/MouseTarget"};
    QString session_;
    QPointer<KWin::SurfaceInterface> last_surface_;
    QString surface_token_;
    bool object_registered_{false};
    bool service_registered_{false};
};

TargetAdaptor::TargetAdaptor(TargetEffect* effect)
    : QDBusAbstractAdaptor{effect}, effect_{effect} {}

QString TargetAdaptor::target() { return effect_->snapshot(); }

KWIN_EFFECT_FACTORY_SUPPORTED(TargetEffect, "metadata.json", return KWin::waylandServer() != nullptr;)

} // namespace dotfiles::mouse

#include "kwin.moc"
