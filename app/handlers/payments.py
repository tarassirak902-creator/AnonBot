from .shared import *
from app.core.games import GAME_NAMES, TELEGRAM_DICE_EMOJIS, solo_native_win, play_custom_solo, play_custom_duel

async def _resolve_question_payment_receiver(user_id: int, context: str, reference: str) -> int | None:
    receiver_id: int | None = None
    if context == "t":
        try:
            candidate = int(reference)
        except (TypeError, ValueError):
            candidate = 0
        if candidate and candidate != user_id and await db.get_question_owner_by_id(candidate):
            receiver_id = candidate
    elif context in {"q", "a"}:
        question = await db.get_question_by_public_id(reference)
        if question:
            if context == "q" and int(question[3]) == user_id:
                receiver_id = int(question[2])
            elif context == "a" and int(question[2]) == user_id:
                receiver_id = int(question[3])
    return receiver_id


# =====================================================================
# 6. ОБРАБОТКА ОПЛАТЫ И VIP ПОДПИСКИ (TELEGRAM STARS)
# =====================================================================

@router.pre_checkout_query()
async def pre_checkout(pre_checkout: PreCheckoutQuery):
    await pre_checkout.answer(ok=True)

@router.message(F.successful_payment)
async def successful_payment(message: Message):
    user_id = message.from_user.id
    payment = message.successful_payment
    payload = payment.invoice_payload

    invoice_message_id = pending_invoice_message_ids.pop(user_id, None)
    if invoice_message_id:
        try:
            await message.bot.delete_message(message.chat.id, invoice_message_id)
        except Exception:
            pass
    if invoice_message_id or payload.startswith("solo_") or payload.startswith("vip_subscription"):
        try:
            await message.delete()
        except Exception:
            pass

    if payload.startswith("ad_order_"):
        order_id = int(payload.rsplit("_", 1)[1])
        charge_id = payment.telegram_payment_charge_id
        activated = await db.activate_ad_order(order_id, user_id, charge_id)
        if activated:
            await message.answer(
                f"✅ <b>Рекламная кампания №{order_id} оплачена и автоматически запущена.</b>",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(
                            text="👁 Открыть заказ",
                            callback_data=f"ads_order_view_{order_id}",
                        )],
                        [InlineKeyboardButton(
                            text="📋 Мои заказы",
                            callback_data="ads_my_orders",
                        )],
                    ]
                ),
            )
            for admin_id in ADMIN_IDS:
                try:
                    await message.bot.send_message(
                        admin_id,
                        f"✅ Реклама по заявке №{order_id} оплачена и работает.",
                    )
                except Exception:
                    logger.exception(
                        "Не удалось уведомить администратора об оплате рекламы: "
                        "admin_id=%s, order_id=%s, user_id=%s",
                        admin_id,
                        order_id,
                        user_id,
                    )
        else:
            await message.answer("Платёж получен, но заявка уже была активирована или недоступна. Обратитесь в /paysupport.")

    elif payload.startswith("question_stars:"):
        try:
            _, context, reference, amount_raw = payload.split(":", 3)
            amount = int(amount_raw)
        except (TypeError, ValueError):
            await message.answer("Платёж получен, но данные повреждены. Обратитесь в /paysupport.")
            await db.log_action(user_id, "question_stars_invalid", payload)
            return

        receiver_id = await _resolve_question_payment_receiver(user_id, context, reference)
        if not receiver_id or amount < 1 or amount > 10000 or int(payment.total_amount) != amount:
            await message.answer("Платёж получен, но получатель или сумма недоступны. Обратитесь в /paysupport.")
            await db.log_action(user_id, "question_stars_invalid", payload)
            return

        await db.add_user_balance(receiver_id, amount)
        await db.update_user_stats(user_id, stars=amount)
        await db.add_purchase(user_id, receiver_id, 0, amount, "question_stars")
        await db.log_action(user_id, "question_stars_sent", f"receiver_id={receiver_id}; stars={amount}")
        try:
            await message.bot.send_message(
                receiver_id,
                "⭐ <b>Вам анонимно подарили звёзды!</b>\n\n"
                "Источник:\n❓ Анонимные вопросы\n\n"
                f"Количество: <b>{amount} ⭐</b>",
                parse_mode="HTML",
            )
        except Exception as exc:
            await db.log_action(user_id, "question_stars_notify_error", f"receiver_id={receiver_id}; error={exc}")

        await message.answer(
            "✅ <b>Звёзды успешно отправлены!</b>\n\n"
            "Получатель уже получил уведомление.\n\n"
            "Ваше имя осталось анонимным.",
            parse_mode="HTML",
        )

    elif payload.startswith("question_premium:"):
        try:
            _, context, reference, months_raw, stars_raw = payload.split(":", 4)
            months, stars = int(months_raw), int(stars_raw)
        except (TypeError, ValueError):
            await message.answer("Платёж получен, но данные Telegram Premium повреждены. Обратитесь в /paysupport.")
            await db.log_action(user_id, "question_premium_invalid", payload)
            return

        allowed = {3: 1000, 6: 1500, 12: 2500}
        receiver_id = await _resolve_question_payment_receiver(user_id, context, reference)
        if not receiver_id or allowed.get(months) != stars or int(payment.total_amount) != stars:
            await message.answer("Платёж получен, но получатель или вариант Telegram Premium недоступны. Обратитесь в /paysupport.")
            await db.log_action(user_id, "question_premium_invalid", payload)
            return

        try:
            await message.bot.gift_premium_subscription(
                user_id=receiver_id,
                month_count=months,
                star_count=stars,
                text="Анонимный подарок через вопросы Casper 💜",
            )
        except Exception as exc:
            await db.log_action(
                user_id,
                "question_premium_delivery_error",
                f"receiver_id={receiver_id}; months={months}; stars={stars}; error={exc}",
            )
            await message.answer(
                "Оплата прошла, но Telegram Premium не удалось выдать автоматически. "
                "Обратитесь в /paysupport — платёж сохранён.",
            )
            return

        await db.update_user_stats(user_id, stars=stars)
        await db.add_purchase(user_id, receiver_id, 0, stars, "question_premium")
        await db.log_action(user_id, "question_premium_sent", f"receiver_id={receiver_id}; months={months}; stars={stars}")
        try:
            await message.bot.send_message(
                receiver_id,
                "💎 <b>Вам анонимно подарили Telegram Premium!</b>\n\n"
                "Источник:\n❓ Анонимные вопросы\n\n"
                f"Срок: <b>{months} месяцев</b>",
                parse_mode="HTML",
            )
        except Exception as exc:
            await db.log_action(user_id, "question_premium_notify_error", f"receiver_id={receiver_id}; error={exc}")

        await message.answer(
            "✅ <b>Telegram Premium успешно подарен!</b>\n\n"
            "Получатель уже получил подписку.\n\n"
            "Ваше имя осталось анонимным.",
            parse_mode="HTML",
        )

    elif payload.startswith("question_vip:"):
        try:
            _, context, reference, days_raw = payload.split(":", 3)
            days = int(days_raw)
        except (TypeError, ValueError):
            await message.answer("Платёж получен, но данные VIP повреждены. Обратитесь в /paysupport.")
            await db.log_action(user_id, "question_vip_invalid", payload)
            return

        receiver_id = None
        if context == "t":
            try:
                candidate = int(reference)
            except ValueError:
                candidate = 0
            if candidate and candidate != user_id and await db.get_question_owner_by_id(candidate):
                receiver_id = candidate
        elif context in {"q", "a"}:
            question = await db.get_question_by_public_id(reference)
            if question:
                if context == "q" and int(question[3]) == user_id:
                    receiver_id = int(question[2])
                elif context == "a" and int(question[2]) == user_id:
                    receiver_id = int(question[3])

        if not receiver_id or days != 30:
            await message.answer("Платёж получен, но получатель VIP недоступен. Обратитесь в /paysupport.")
            await db.log_action(user_id, "question_vip_invalid", payload)
            return

        paid_price = int(payment.total_amount)
        await db.extend_user_vip_days(receiver_id, days=days)
        try:
            await message.bot.send_message(
                receiver_id,
                "👑 <b>Вам анонимно подарили VIP статус!</b>\n\n"
                "Источник:\n❓ Анонимные вопросы\n\n"
                f"Срок: <b>{days} дней</b>",
                parse_mode="HTML",
            )
        except Exception as exc:
            await db.log_action(
                user_id,
                "question_vip_notify_error",
                f"receiver_id={receiver_id}; days={days}; error={exc}",
            )

        await db.update_user_stats(user_id, stars=paid_price)
        await db.add_purchase(user_id, receiver_id, 0, paid_price, "question_vip")
        await db.log_action(user_id, "question_vip_sent", f"receiver_id={receiver_id}; days={days}; stars={paid_price}")
        await message.answer(
            "✅ <b>VIP статус успешно подарен!</b>\n\nПолучатель уже получил уведомление.\n\nВаше имя осталось анонимным.",
            parse_mode="HTML",
        )

    elif payload == "vip_subscription_100" or payload.startswith("vip_subscription"):
        await db.extend_user_vip_days(user_id, days=30)
        await message.answer("👑 <b>Поздравляем! VIP подписка успешно активирована/продлена на 1 месяц!</b>\n\nВам доступна скидка 30% на все подарки и полная защита от авто-ограничений.", parse_mode="HTML")

    elif payload.startswith("solo_"):
        parts = payload.split("_")
        game_type = parts[1]
        bet = int(parts[2])

        dice_msg = None
        if game_type in TELEGRAM_DICE_EMOJIS:
            dice_msg = await message.bot.send_dice(message.chat.id, emoji=TELEGRAM_DICE_EMOJIS[game_type])
            await asyncio.sleep(4)
            value = dice_msg.dice.value
            win = solo_native_win(game_type, value, bet)
            result_text = f"Результат: <b>{value}</b>."
        else:
            win, result_text = play_custom_solo(game_type, bet)

        if dice_msg:
            try:
                await dice_msg.delete()
            except Exception:
                pass

        result_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Сыграть ещё раз", callback_data=f"solo_replay_{game_type}_{bet}")],
            [InlineKeyboardButton(text="↩️ Назад к выбору игр", callback_data="solo_result_games")],
        ])
        if win > 0:
            await db.add_user_balance(user_id, win)
            await message.bot.send_message(
                message.chat.id,
                f"🎉 <b>Результат игры</b>\n\n{result_text}\n\n"
                f"На ваш баланс зачислено <b>+{win} ⭐</b>.",
                parse_mode="HTML",
                reply_markup=result_kb,
            )
        else:
            await message.bot.send_message(
                message.chat.id,
                f"💔 <b>Результат игры</b>\n\n{result_text}\n\n"
                "В этот раз выиграть не удалось.",
                parse_mode="HTML",
                reply_markup=result_kb,
            )

    elif payload.startswith("duel_create_"):
        parts = payload.split("_")
        partner_id = int(parts[2])
        bet = int(parts[3])
        game_type = parts[4] if len(parts) > 4 else "darts"

        duel_id = await db.create_game_duel(user_id, partner_id, bet, game_type)
        await message.answer(
            f"⏳ Ваша ставка <b>{bet} ⭐</b> оплачена! Ожидаем ответа собеседника...",
            parse_mode="HTML",
        )

        duel_kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text=f"✅ Принять и оплатить {bet} ⭐", callback_data=f"pay_duel_accept_{duel_id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"decline_duel_{duel_id}"),
            ]
        ])
        game_title = GAME_NAMES.get(game_type, "Дуэль")

        try:
            await message.bot.send_message(
                partner_id,
                f"⚔️ <b>Собеседник вызывает вас на дуэль «{game_title}»!</b>\n\n"
                f"Ставка каждого игрока: <b>{bet} ⭐</b>.\n"
                "Победитель получает игровой банк на баланс профиля.",
                parse_mode="HTML",
                reply_markup=duel_kb,
            )
        except Exception:
            logger.exception(
                "Не удалось отправить дуэльный вызов: "
                "user_id=%s, partner_id=%s, game_type=%s, bet=%s",
                user_id,
                partner_id,
                game_type,
                bet,
            )
            await message.answer(
                "Не удалось отправить вызов собеседнику."
            )

    elif payload.startswith("duel_accept_"):
        duel_id = int(payload.split("_")[2])
        duel = await db.get_game_duel(duel_id)

        if not duel or duel[4] != "waiting":
            await message.answer("Дуэль недействительна.")
            return

        creator_id = duel[1]
        partner_id = duel[2]
        bet = duel[3]
        game_type = duel[5] if len(duel) > 5 and duel[5] else "darts"
        game_title = GAME_NAMES.get(game_type, "Дуэль")

        await db.update_game_duel_status(duel_id, "active")
        bot = message.bot

        for uid in (creator_id, partner_id):
            await bot.send_message(
                uid,
                f"🚀 <b>Дуэль «{game_title}» началась!</b>\n"
                f"Обе ставки по {bet} ⭐ оплачены.",
                parse_mode="HTML",
            )

        if game_type in TELEGRAM_DICE_EMOJIS:
            emoji = TELEGRAM_DICE_EMOJIS[game_type]
            msg1 = await bot.send_dice(creator_id, emoji=emoji)
            msg2 = await bot.send_dice(partner_id, emoji=emoji)
            await asyncio.sleep(4)
            val1, val2 = msg1.dice.value, msg2.dice.value
            result_text = f"Результаты: <b>{val1}</b> против <b>{val2}</b>."
        else:
            val1, val2, result_text = play_custom_duel(game_type)

        total_pot = bet * 2
        win_amount = int(total_pot * 0.90)

        if val1 > val2:
            await db.add_user_balance(creator_id, win_amount)
            await bot.send_message(
                creator_id,
                f"🏆 <b>Вы победили!</b>\n{result_text}\n\n"
                f"На баланс начислено <b>+{win_amount} ⭐</b>.",
                parse_mode="HTML",
            )
            await bot.send_message(partner_id, f"💔 <b>Вы проиграли.</b>\n{result_text}", parse_mode="HTML")
        elif val2 > val1:
            await db.add_user_balance(partner_id, win_amount)
            await bot.send_message(
                partner_id,
                f"🏆 <b>Вы победили!</b>\n{result_text}\n\n"
                f"На баланс начислено <b>+{win_amount} ⭐</b>.",
                parse_mode="HTML",
            )
            await bot.send_message(creator_id, f"💔 <b>Вы проиграли.</b>\n{result_text}", parse_mode="HTML")
        else:
            await db.add_user_balance(creator_id, bet)
            await db.add_user_balance(partner_id, bet)
            for uid in (creator_id, partner_id):
                await bot.send_message(
                    uid,
                    f"🤝 <b>Ничья!</b>\n{result_text}\n\n"
                    f"Ставка <b>{bet} ⭐</b> возвращена на баланс профиля.",
                    parse_mode="HTML",
                )

        await db.update_game_duel_status(duel_id, "completed")

    elif payload.startswith("question_reveal:"):
        public_id = payload.split(":", 1)[1]
        question = await db.get_question_by_public_id(public_id)
        if not question or int(question[3]) != user_id:
            await message.answer(
                "Платёж получен, но вопрос недоступен. Обратитесь в /paysupport."
            )
            await db.log_action(user_id, "question_reveal_invalid", payload)
            return

        sender_id = int(question[2])
        await db.mark_question_author_revealed(public_id, user_id)
        await db.update_user_stats(user_id, stars=100)
        await db.add_purchase(user_id, sender_id, 0, 100, "question_reveal")

        try:
            author = await message.bot.get_chat(sender_id)
            full_name = f"{author.first_name or ''} {author.last_name or ''}".strip() or "Не указано"
            username = f"@{author.username}" if author.username else "Не установлен"
            await message.answer(
                "✅ <b>Автор вопроса раскрыт</b>\n\n"
                f"Имя: <b>{full_name}</b>\n"
                f"Username: <b>{username}</b>\n"
                f"Telegram ID: <code>{author.id}</code>\n\n"
                f'<a href="tg://user?id={author.id}">Открыть профиль</a>',
                parse_mode="HTML",
                reply_markup=question_card_menu(author_revealed=True),
            )
        except Exception:
            await message.answer(
                f'✅ Автор раскрыт: <a href="tg://user?id={sender_id}">открыть профиль</a>',
                parse_mode="HTML",
                reply_markup=question_card_menu(author_revealed=True),
            )

    elif payload.startswith("question_gift:"):
        try:
            _, context, reference, gift_id_raw = payload.split(":", 3)
            gift_id = int(gift_id_raw)
        except (TypeError, ValueError):
            await message.answer("Платёж получен, но данные подарка повреждены. Обратитесь в /paysupport.")
            await db.log_action(user_id, "question_gift_invalid", payload)
            return

        receiver_id = None
        if context == "t":
            try:
                candidate = int(reference)
            except ValueError:
                candidate = 0
            if candidate and candidate != user_id and await db.get_question_owner_by_id(candidate):
                receiver_id = candidate
        elif context in {"q", "a"}:
            question = await db.get_question_by_public_id(reference)
            if question:
                if context == "q" and int(question[3]) == user_id:
                    receiver_id = int(question[2])
                elif context == "a" and int(question[2]) == user_id:
                    receiver_id = int(question[3])

        gift = await db.get_gift(gift_id)
        if not receiver_id or not gift:
            await message.answer("Платёж получен, но подарок или получатель недоступен. Обратитесь в /paysupport.")
            await db.log_action(user_id, "question_gift_invalid", payload)
            return

        name, emoji, _base_price = gift
        paid_price = int(payment.total_amount)
        try:
            await message.bot.send_message(
                receiver_id,
                "🎁 <b>Вам анонимно подарили подарок!</b>\n\n"
                "Источник:\n❓ Анонимные вопросы\n\n"
                f"Стоимость: ⭐{paid_price}",
                parse_mode="HTML",
            )
        except Exception as exc:
            await db.log_action(
                user_id,
                "question_gift_notify_error",
                f"receiver_id={receiver_id}; gift_id={gift_id}; error={exc}",
            )

        await db.update_user_stats(user_id, sent_gifts=1, stars=paid_price)
        await db.update_user_stats(receiver_id, received_gifts=1)
        await db.add_purchase(user_id, receiver_id, gift_id, paid_price, "question_gift")
        await message.answer(
            "✅ <b>Подарок успешно отправлен!</b>\n\nПолучатель уже получил уведомление.\n\nВаше имя осталось анонимным.",
            parse_mode="HTML",
        )

    elif payload.startswith("gift_"):
        _, gift_id, receiver_id = payload.split("_")
        gift_id, receiver_id = int(gift_id), int(receiver_id)
        gift = await db.get_gift(gift_id)
        if gift:
            name, emoji, price = gift
            try:
                paid_price = int(payment.total_amount)
                await message.bot.send_message(
                    receiver_id,
                    "🎁 <b>Вам анонимно подарили подарок!</b>\n\n"
                    "Источник:\n💬 Анонимный чат\n\n"
                    f"Стоимость: ⭐{paid_price}",
                    parse_mode="HTML",
                )
            except Exception as exc:
                await db.log_action(
                    user_id,
                    "gift_notify_error",
                    f"receiver_id={receiver_id}; gift_id={gift_id}; error={exc}",
                )
            paid_price = int(payment.total_amount)
            await db.update_user_stats(user_id, sent_gifts=1, stars=paid_price)
            await db.update_user_stats(receiver_id, received_gifts=1)
            await db.add_purchase(user_id, receiver_id, gift_id, paid_price, "gift")

    elif payload.startswith("reveal_"):
        _, partner_id = payload.split("_")
        partner_id = int(partner_id)
        cost = int(await db.get_setting("reveal_cost"))
        partner_user = await message.bot.get_chat(partner_id)
        name = f"{partner_user.first_name or ''} {partner_user.last_name or ''}".strip()
        username = f"@{partner_user.username}" if partner_user.username else f"ID {partner_user.id}"
        await message.answer(f"<b>Ваш собеседник:</b>\nИмя: {name}\nUsername: {username}\nTelegram ID: {partner_user.id}", parse_mode="HTML")
        await db.update_user_stats(user_id, stars=cost)
        await db.add_purchase(user_id, partner_id, 0, cost, "reveal")

    await db.log_action(user_id, "successful_payment", payload)


