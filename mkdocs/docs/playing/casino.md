# How to play the Casino

When your ship is in the hangar bay, open the **Casino** tab. Inside is a
lobby: pick a room from the list on the left, read its blurb, and hit **Play**.
There's a **bar**, eight **games**, and a **pilot market**.

## Chips

Everything is played with **chips**. You start with a small stack, and the
**cage** at the top of the lobby lets you **Buy** more or **Cash Out**. Buying
uses your chips first, then dips into the crew's shared credits, so you can
always get back in the game. Win enough over a session and the house sends over
**comp** chips as a thank-you.

## The bar

Grab a drink from **Bitters**, toast the room, and chat with the regulars.
Select a patron to see them and either **buy them a drink** or **ask for a
rumor**. A rumor is a tip; **act on it** to see if it pans out. Some pilots are
more reliable than others &mdash; and a patron who steers you wrong loses your
trust, while one who comes through earns it. Build enough trust and the pilot
market's **grey market** opens up.

---

## The games

### Parity &mdash; the quick one

Three cards' values are XOR'd together into a **register** from 0 to 15.

1. Pick a bet: **Even** or **Odd**, or **High** (8-15) or **Low** (0-7).
2. The cards flip and the register is revealed.
3. Guess right and you win an even-money payout.

Fast, simple, and a fair shake &mdash; a good place to warm up.

### Blackjack

Classic 21 on a standard deck.

1. You and the dealer are dealt two cards; one of the dealer's is hidden.
2. **Hit** to take another card or **Stand** to hold. Aces count as 1 or 11.
3. Get closer to **21** than the dealer without going over (a "bust").

A two-card 21 is a **blackjack** and pays extra (3 to 2). The dealer must keep
hitting until 17.

### Video Poker (Jacks or Better)

Just you and the paytable &mdash; no dealer.

1. You're dealt **five cards**.
2. **Tap the cards** you want to keep &mdash; each shows **HELD**.
3. Press **Draw** to replace the rest.
4. Your final hand is paid by the table shown at the top.

A pair of **Jacks or better** returns your bet; it climbs from there &mdash;
two pair, three of a kind, straight, flush, full house, four of a kind, straight
flush, and a **Royal Flush pays 250x**.

### Nibble &mdash; a tough table

An Arvonian cousin of blackjack. Beat the dealer with the **highest hand of 20
or less**.

1. **Hit** to draw, **Stand** to hold.
2. Your score is each card's number **plus** its filled-in **castles** &mdash;
   and castles count for more on every later card, so pressing your luck adds up
   fast.
3. Go over 20 and you bust.

The house here plays a friendlier version than the old Arvonian rules: **ties
go to you**, and the dealer stops drawing sooner. Start with two 0s or two 7s
for a **natural** that pays double. Even so, the castle scoring makes this the
house's toughest table &mdash; play it steady.

### Gates

An Arvonian logic game &mdash; you **bet on which hand wins**, you don't play a
hand yourself.

1. Two hands are dealt: **Player** and **Banker**. Each is a bit card, a logic
   gate **printed on the card** (AND, OR, NOR, or NAND), and another bit card.
2. Bet **Bet Player** or **Bet Banker**.
3. Each hand's score is `first-bit GATE second-bit` (0-7). Highest total wins;
   the **Banker wins ties**.

### Choga &mdash; Soul Tickle

Arvonian stud poker against **the Understander** (the house computer).

1. Ante up. You get **five cards**; the Understander shows one.
2. Look at your hand and decide: **Raise** (put up double) or **Fold** (give up
   the ante).
3. Best poker hand wins. The Understander only plays with a **pair or better**
   &mdash; if it can't, your ante pays and your raise is returned.

A special Arvonian twist: if your five card values **XOR to zero** ("a clean
checksum"), you collect a bonus on top. And a quirk of this 64-card deck &mdash;
a **straight beats a flush** here, the opposite of a normal deck.

### KoraTa &mdash; Ghost-Writing

A five-round duel against the Understander's **apprentice**. You each build a
scoring **run** from your cards &mdash; and the gates those cards carry let you
**sabotage** the other run.

1. You get a hand of cards and play one each round, over **five rounds** in the
   fixed order **Value, Opcode, Value, Opcode, Value**.
2. On a **Value** round, play a card for its **number** to extend your own run.
3. On an **Opcode** round, play a card for the **gate printed on it** to fold
   into &mdash; and corrupt &mdash; the apprentice's run.
4. Bet across **two streets** during the duel. The **higher final score takes
   the pot**.

Two tables to choose from: the **3-bit** game runs values 0-7 (tighter scores,
more ties), and the **4-bit** game runs 0-15 (bigger swings, fewer ties).

---

## The pilot market

Spend your winnings on real gear. Browse the list, **Buy** what you want, or
**Sell** something back (for less than you paid). Craft upgrades are pricey on
purpose &mdash; a big one might cost more chips than you can hold, so it draws on
the crew's shared credits too. Earn a patron's trust at the bar and the
**grey market** stocks the rare stuff.
