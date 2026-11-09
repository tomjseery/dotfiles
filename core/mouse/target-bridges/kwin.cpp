// SPDX-License-Identifier: GPL-2.0-or-later
#include "effect/effect.h"
#include "effect/effecthandler.h"
#include "input.h"
#include "pointer_input.h"
#include "wayland/pointer.h"
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

#include <limits>

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

Q_SIGNALS:
    void changed(const QString& session, qulonglong generation);

private:
    TargetEffect* effect_;
};

class TargetEffect final : public KWin::Effect {
    Q_OBJECT

public:
    TargetEffect()
        : session_{QUuid::createUuid().toString(QUuid::WithoutBraces)} {
        adaptor_ = new TargetAdaptor{this};
        auto* server{KWin::waylandServer()};
        auto* seat{server ? server->seat() : nullptr};
        if (seat && seat->pointer()) {
            watched_pointer_ = seat->pointer();
            connect(watched_pointer_.data(), &KWin::PointerInterface::focusedSurfaceChanged,
                    this, [this] { invalidate(); });
            connect(seat, &KWin::SeatInterface::dragStarted, this, [this] { invalidate(); });
            connect(seat, &KWin::SeatInterface::dragEnded, this, [this] { invalidate(); });
            connect(seat, &KWin::SeatInterface::hasPointerChanged, this, [this] { invalidate(); });
        }
        if (KWin::effects) {
            connect(KWin::effects, &KWin::EffectsHandler::screenLockingChanged,
                    this, [this] { invalidate(); });
            connect(KWin::effects, &KWin::EffectsHandler::hasActiveFullScreenEffectChanged,
                    this, [this] { invalidate(); });
        }
        if (KWin::input() && KWin::input()->pointer())
            connect(KWin::input()->pointer(), &KWin::InputDeviceHandler::decorationChanged,
                    this, [this] { invalidate(); });
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
        invalidate();
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
        if (generation_exhausted_ || !effects || !input || !server || effects->isScreenLocked()
            || effects->hasActiveFullScreenEffect() || effects->isMouseInterception()
            || effects->hasKeyboardGrab() || input->isSelectingWindow())
            return unknown();

        auto* pointer{input->pointer()};
        auto* seat{server->seat()};
        if (!pointer || !seat || !watched_pointer_ || watched_pointer_ != seat->pointer()
            || seat->isDrag() || pointer->isConstrained()
            || pointer->areButtonsPressed() || pointer->decoration())
            return unknown();
        auto* window{pointer->focus()};
        auto* surface{watched_pointer_->focusedSurface()};
        // Restrict this version to root application surfaces. Popups, subsurfaces,
        // compositor surfaces and decoration targets remain native.
        if (!window || !surface || pointer->hover() != window
            || window->isDeleted() || !window->isShown()
            || !window->isNormalWindow() || window->isInteractiveMove()
            || window->isInteractiveResize() || !surface->isMapped()
            || surface != window->surface() || window->resourceClass().isEmpty())
            return unknown();

        if (last_surface_.data() != surface) {
            disconnect(class_connection_);
            class_connection_ = connect(window, &KWin::Window::windowClassChanged,
                                        this, [this] { invalidate(); });
            last_surface_ = surface;
            surface_token_ = window->internalId().toString(QUuid::WithoutBraces)
                + QLatin1Char('/') + QString::number(generation_) + QLatin1Char('/')
                + QUuid::createUuid().toString(QUuid::WithoutBraces);
        }
        const QJsonObject result{{QStringLiteral("session"), session_},
                                 {QStringLiteral("surface"), surface_token_},
                                 {QStringLiteral("app"), window->resourceClass()}};
        return QString::fromUtf8(QJsonDocument{result}.toJson(QJsonDocument::Compact));
    }

private:
    void invalidate() {
        // Advance for each compositor notification, even if a query never saw
        // the intervening surface in an A -> B -> A excursion.
        if (generation_ == std::numeric_limits<qulonglong>::max())
            generation_exhausted_ = true;
        else
            ++generation_;
        last_surface_.clear();
        surface_token_.clear();
        disconnect(class_connection_);
        Q_EMIT adaptor_->changed(session_, generation_);
    }

    static constexpr auto service_name{"org.tomjseery.MouseTarget"};
    static constexpr auto object_path{"/MouseTarget"};
    QString session_;
    TargetAdaptor* adaptor_{nullptr};
    QPointer<KWin::PointerInterface> watched_pointer_;
    QMetaObject::Connection class_connection_;
    qulonglong generation_{0};
    bool generation_exhausted_{false};
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
