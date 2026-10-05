// SPDX-License-Identifier: GPL-2.0-or-later
// Use KWin's normal themed pointer, not a scene overlay, during midscroll.

#include "cursor.h"
#include "cursorsource.h"
#include "effect/effect.h"
#include "effect/effecthandler.h"
#include "utils/cursortheme.h"

#include <QLocalSocket>
#include <QPointer>
#include <QTimer>

#include <cmath>

namespace KWin
{

class MidscrollCursorEffect : public Effect
{
    Q_OBJECT

public:
    MidscrollCursorEffect()
        : m_cursor(Cursors::self()->mouse())
    {
        // Cursor::setSource() only stores a raw pointer. Keep this source
        // alive for the cursor's whole lifetime, not just one scroll, so a
        // queued paint cannot observe an object freed at scroll end.
        m_override = new ShapeCursorSource(m_cursor.data());
        m_retry.setInterval(2000);
        connect(&m_retry, &QTimer::timeout, this, [this]() { connectSocket(); });
        connect(&m_socket, &QLocalSocket::readyRead, this, [this]() { readSocket(); });
        connect(&m_socket, &QLocalSocket::disconnected, this, [this]() {
            setScrolling(false);
            m_input.clear();
        });
        connect(m_cursor.data(), &Cursor::posChanged, this, [this]() { updateDirection(); });
        connect(m_cursor.data(), &Cursor::cursorChanged, this, [this]() {
            // KWin may change the client cursor while crossing windows. Keep
            // the override only during this scroll, and remember the latest
            // client cursor so it can be restored when scrolling stops.
            if (m_scrolling && m_override && m_cursor->source() != m_override.data()) {
                m_original = m_cursor->source();
                m_cursor->setSource(m_override.data());
            }
        });
        connect(effects, &EffectsHandler::screenLockingChanged, this,
                [this](bool locked) {
                    if (locked) {
                        setScrolling(false);
                    }
                });
        m_retry.start();
        connectSocket();
    }

    ~MidscrollCursorEffect() override
    {
        // The cursor source belongs to Cursor, not this unloadable effect.
        // Do not mutate Cursor during effect destruction: KWin may be in the
        // middle of dispatching an effect/cursor signal at that point.
        disconnect(&m_socket, nullptr, this, nullptr);
        if (m_cursor) {
            disconnect(m_cursor.data(), nullptr, this, nullptr);
        }
    }

    // This effect changes only the normal pointer image; it does not paint.
    bool isActive() const override
    {
        return false;
    }

private:
    void connectSocket()
    {
        if (m_socket.state() == QLocalSocket::UnconnectedState) {
            const QString path = qEnvironmentVariable(
                "MIDSCROLL_CURSOR_STATE_SOCKET",
                "/run/midscroll/state.sock");
            m_socket.connectToServer(path);
        }
    }

    void readSocket()
    {
        m_input += m_socket.readAll();
        if (m_input.size() > 8192) {
            m_socket.abort();
            m_input.clear();
            setScrolling(false);
            return;
        }
        qsizetype end;
        while ((end = m_input.indexOf('\n')) >= 0) {
            const QByteArray line = m_input.left(end).trimmed();
            m_input.remove(0, end + 1);
            if (line == "1") {
                setScrolling(true);
            } else if (line == "0") {
                setScrolling(false);
            }
        }
    }

    void setScrolling(bool scrolling)
    {
        if (!m_cursor || !m_override || scrolling == m_scrolling
            || (scrolling && effects->isScreenLocked())) {
            return;
        }
        if (!scrolling) {
            m_scrolling = false;
            if (m_cursor->source() == m_override.data()) {
                m_cursor->setSource(m_original.data());
            }
            m_original.clear();
            return;
        }

        // Use the active theme's real pointer source. Unlike an ImageItem this
        // goes through KWin's ordinary cursor path and never paints a scene.
        m_theme = CursorTheme(m_cursor->themeName(), m_cursor->themeSize(), 1);
        if (m_theme.shape("up-arrow").isEmpty()) {
            // Custom themes need not provide autoscroll arrows. Breeze is a
            // KWin dependency and keeps the pointer visible in that case.
            m_theme = CursorTheme(QStringLiteral("breeze_cursors"),
                                  m_cursor->themeSize(), 1);
        }
        if (m_theme.shape("up-arrow").isEmpty()) {
            return;
        }
        m_override->setTheme(m_theme);
        m_override->setShape(QByteArrayLiteral("up-arrow"));
        m_original = m_cursor->source();
        m_origin = m_cursor->pos();
        m_direction = 0;
        m_scrolling = true;
        m_cursor->setSource(m_override.data());
    }

    void updateDirection()
    {
        if (!m_scrolling || !m_cursor || !m_override) {
            return;
        }
        const QPointF delta = m_cursor->pos() - m_origin;
        QByteArray shape = "up-arrow";
        int direction = 0;
        if (std::abs(delta.x()) > 15 || std::abs(delta.y()) > 15) {
            if (std::abs(delta.x()) > std::abs(delta.y())) {
                direction = delta.x() > 0 ? 1 : 3;
                shape = delta.x() > 0 ? "right-arrow" : "left-arrow";
            } else if (delta.y() > 0) {
                direction = 2;
                shape = "down-arrow";
            }
        }
        if (direction != m_direction) {
            m_direction = direction;
            if (m_theme.shape(shape).isEmpty()) {
                shape = "up-arrow";
            }
            m_override->setShape(shape);
        }
    }

    QPointer<Cursor> m_cursor;
    QLocalSocket m_socket;
    QTimer m_retry;
    QByteArray m_input;
    CursorTheme m_theme;
    QPointer<ShapeCursorSource> m_override;
    QPointer<CursorSource> m_original;
    QPointF m_origin;
    int m_direction = 0;
    bool m_scrolling = false;
};

KWIN_EFFECT_FACTORY_SUPPORTED(MidscrollCursorEffect,
                              "metadata.json",
                              return effects->isOpenGLCompositing();)

} // namespace KWin

#include "midscrollcursor.moc"
