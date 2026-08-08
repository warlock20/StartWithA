/**
 * =============================================================================
 * THESIS HOVER CARD
 * =============================================================================
 *
 * Floating detail view for the idea inbox thesis column. Hover opens it,
 * click pins it (which is also the only way to reach it on touch).
 *
 * Two constraints drive the design:
 *
 *   1. Tabulator sets `overflow: hidden` on `.tabulator-cell`, so a card
 *      rendered inside the cell is clipped. The card is mounted on
 *      `document.body` and positioned `fixed`.
 *   2. Tabulator virtualises rows — sorting, filtering, paginating and
 *      scrolling destroy and rebuild row DOM. All listeners are delegated to
 *      a stable container so nothing ever needs re-binding.
 *
 * Usage:
 *   var card = initThesisHoverCard({
 *       container: '#inbox-table',
 *       lookup: function (id) { return ideaMap[id]; }
 *   });
 *   card.close();
 */
(function (window, document) {
    'use strict';

    var CLOSE_DELAY = 120;   // ms grace to travel from cell to card
    var EDGE_GAP = 8;        // px clearance from the viewport edge
    var TRIGGER = '.idea-thesis-cell.has-detail';

    function escapeHtml(value) {
        return String(value == null ? '' : value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function initThesisHoverCard(options) {
        var container = typeof options.container === 'string'
            ? document.querySelector(options.container)
            : options.container;
        if (!container) return null;

        var lookup = options.lookup;
        var card, scrollEl, footEl, hintEl, closeBtn;
        var pinned = false;
        var pinnedByFocus = false;
        var activeTrigger = null;
        var closeTimer = null;
        var pointerDown = false;
        var suppressFocusPin = false;

        function build() {
            card = document.createElement('div');
            card.className = 'thesis-card';
            card.id = 'thesis-hover-card';
            card.setAttribute('role', 'dialog');
            card.setAttribute('aria-label', 'Idea thesis and notes');
            card.innerHTML =
                '<div class="tc-scroll" tabindex="0"></div>' +
                '<div class="tc-foot">' +
                '<span class="tc-hint"></span>' +
                '<button type="button" class="tc-close">Close</button>' +
                '</div>';
            document.body.appendChild(card);

            scrollEl = card.querySelector('.tc-scroll');
            footEl = card.querySelector('.tc-foot');
            hintEl = card.querySelector('.tc-hint');
            closeBtn = card.querySelector('.tc-close');

            // Keep it open while the pointer is inside, so it can be scrolled.
            card.addEventListener('pointerenter', function () {
                clearTimeout(closeTimer);
            });
            card.addEventListener('pointerleave', function () {
                if (!pinned) close();
            });
            closeBtn.addEventListener('click', close);
        }

        function render(trigger) {
            var data = lookup(trigger.getAttribute('data-idea-id')) || {};
            if (!data.thesis && !data.notes) return false;
            var html = '';
            if (data.thesis) {
                html += '<div class="tc-sec">' +
                        '<p class="tc-label">Initial thesis</p>' +
                        '<p class="tc-body">' + escapeHtml(data.thesis) + '</p>' +
                        '</div>';
            }
            if (data.notes) {
                html += '<div class="tc-sec">' +
                        '<p class="tc-label">Initial notes</p>' +
                        '<p class="tc-body">' + escapeHtml(data.notes) + '</p>' +
                        '</div>';
            }
            scrollEl.innerHTML = html;
            scrollEl.scrollTop = 0;
            return true;
        }

        function updateFooter() {
            // Only advertise scrolling when the content actually overflows.
            var overflows = scrollEl.scrollHeight > scrollEl.clientHeight + 1;
            if (pinned) {
                hintEl.textContent = 'Escape or click outside to close';
            } else if (overflows) {
                hintEl.textContent = 'Scroll for more · click to pin';
            }
            footEl.style.display = (pinned || overflows) ? 'flex' : 'none';
            closeBtn.style.display = pinned ? '' : 'none';
        }

        function place(trigger) {
            var rect = trigger.getBoundingClientRect();
            // Measure off-screen before committing to a position.
            card.style.left = '-9999px';
            card.style.top = '0px';
            var height = card.offsetHeight;
            var width = card.offsetWidth;

            // Prefer below; flip above when it would cross the bottom edge.
            var top = rect.bottom + EDGE_GAP;
            if (top + height > window.innerHeight - EDGE_GAP) {
                var above = rect.top - height - EDGE_GAP;
                top = above >= EDGE_GAP
                    ? above
                    : Math.max(EDGE_GAP, window.innerHeight - height - EDGE_GAP);
            }

            // Left-align to the cell; shift back inside on the right edge.
            var left = Math.min(rect.left, window.innerWidth - width - EDGE_GAP);
            card.style.left = Math.max(EDGE_GAP, left) + 'px';
            card.style.top = top + 'px';
        }

        function open(trigger) {
            clearTimeout(closeTimer);
            // Render FIRST. With nothing to show, leave every bit of state
            // untouched — marking the trigger active and aria-expanded with no
            // card visible would strand it, and activeTrigger would keep the
            // scroll handler repositioning a hidden card.
            if (!render(trigger)) return false;
            if (activeTrigger && activeTrigger !== trigger) {
                activeTrigger.classList.remove('is-active');
                activeTrigger.setAttribute('aria-expanded', 'false');
            }
            activeTrigger = trigger;
            trigger.classList.add('is-active');
            trigger.setAttribute('aria-expanded', 'true');
            card.classList.add('is-open');
            // Footer first: it changes the card's height, and place() must flip
            // against the final height or a card near the bottom edge overflows.
            updateFooter();
            place(trigger);
            return true;
        }

        function close() {
            clearTimeout(closeTimer);
            pinned = false;
            pinnedByFocus = false;
            card.classList.remove('is-open', 'is-pinned');
            if (activeTrigger) {
                activeTrigger.classList.remove('is-active');
                activeTrigger.setAttribute('aria-expanded', 'false');
            }
            activeTrigger = null;
        }

        function pin(trigger, byFocus) {
            pinned = true;
            pinnedByFocus = !!byFocus;
            // Both flags set before open(), so its updateFooter()/place() pass
            // sees the final pinned geometry and needs no second correction.
            card.classList.add('is-pinned');
            if (!open(trigger)) {
                // Nothing to show. Roll back, or pinned stays true forever and
                // the pointerover handler's early return kills hover for good.
                pinned = false;
                pinnedByFocus = false;
                card.classList.remove('is-pinned');
            }
        }

        function triggerFrom(event) {
            return event.target.closest ? event.target.closest(TRIGGER) : null;
        }

        function toggle(trigger) {
            if (pinned && trigger === activeTrigger) close();
            else pin(trigger, false);
        }

        build();

        container.addEventListener('pointerover', function (e) {
            if (pinned || e.pointerType !== 'mouse') return;
            var trigger = triggerFrom(e);
            if (!trigger) return;
            // Re-entering the same trigger inside the close delay must cancel the
            // pending close — open() only clears the timer when switching triggers.
            clearTimeout(closeTimer);
            if (trigger !== activeTrigger) open(trigger);
        });

        container.addEventListener('pointerout', function (e) {
            if (pinned || e.pointerType !== 'mouse') return;
            var trigger = triggerFrom(e);
            if (!trigger) return;
            var to = e.relatedTarget;
            if (to && (card.contains(to) || trigger.contains(to))) return;
            closeTimer = setTimeout(close, CLOSE_DELAY);
        });

        container.addEventListener('click', function (e) {
            var trigger = triggerFrom(e);
            if (!trigger) return;
            e.preventDefault();
            toggle(trigger);
        });

        container.addEventListener('keydown', function (e) {
            if (e.key !== 'Enter' && e.key !== ' ') return;
            var trigger = triggerFrom(e);
            if (!trigger) return;
            e.preventDefault();
            if (pinned && trigger === activeTrigger) {
                close();
                return;
            }
            pin(trigger, false);
            // A non-focusable scroll region cannot be scrolled by keyboard, and
            // the card sits at the end of <body> so Tab never reaches it. Hand
            // focus over when there is more content than fits.
            if (pinned && scrollEl.scrollHeight > scrollEl.clientHeight + 1) scrollEl.focus();
        });

        // A mouse click focuses the trigger too (it is tabindex="0"), and the
        // event order is pointerdown → focus → focusin → pointerup → click.
        // Without this guard, focusin would pin and the following click would
        // toggle straight back off, making click-to-pin do nothing at all.
        container.addEventListener('pointerdown', function () {
            pointerDown = true;
        });
        document.addEventListener('pointerup', function () {
            pointerDown = false;
        });
        // A pointerup released outside the window never reaches this document.
        // Without these the flag sticks and the keyboard-arrival pin stays dead.
        document.addEventListener('pointercancel', function () {
            pointerDown = false;
        });
        window.addEventListener('blur', function () {
            pointerDown = false;
        });

        // Keyboard arrival pins, so the card cannot evaporate mid-read.
        container.addEventListener('focusin', function (e) {
            if (pinned || pointerDown || suppressFocusPin) return;
            var trigger = triggerFrom(e);
            if (trigger) pin(trigger, true);
        });

        container.addEventListener('focusout', function (e) {
            if (!pinnedByFocus) return;
            var to = e.relatedTarget;
            if (to && card.contains(to)) return;
            close();
        });

        document.addEventListener('click', function (e) {
            if (!pinned || card.contains(e.target)) return;
            if (e.target.closest && e.target.closest(TRIGGER)) return;
            close();
        });

        document.addEventListener('keydown', function (e) {
            if (e.key !== 'Escape' || !activeTrigger) return;
            var trigger = activeTrigger;
            // Restore focus only when it is already inside the widget. Focusing a
            // trigger the user never focused (the plain hover case) fires focusin
            // and would immediately re-pin the card we are trying to close.
            var restoreFocus = document.activeElement === trigger ||
                               card.contains(document.activeElement);
            close();
            if (restoreFocus && trigger && trigger.focus) {
                // focus() fires focusin synchronously, which would re-pin the card
                // we just closed. Suppress the pin for this one restoring focus.
                suppressFocusPin = true;
                trigger.focus();
                suppressFocusPin = false;
            }
        });

        // Capture phase so this still works if the card is ever reused inside a
        // scrolling container. Close rather than let the card drift off-screen
        // when its trigger scrolls out of view.
        window.addEventListener('scroll', function () {
            if (!activeTrigger) return;
            var rect = activeTrigger.getBoundingClientRect();
            if (rect.bottom < 0 || rect.top > window.innerHeight) {
                close();
                return;
            }
            place(activeTrigger);
        }, true);

        return { close: close, element: card };
    }

    window.initThesisHoverCard = initThesisHoverCard;
})(window, document);
