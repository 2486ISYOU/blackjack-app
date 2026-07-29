import streamlit as st
import pandas as pd
import plotly.express as px

# ======================================
# 21點算牌助手 (行動裝置優化版)
# ======================================

st.set_page_config(
    page_title="21點算牌助手",
    page_icon="🃏",
    layout="centered",
    initial_sidebar_state="collapsed"  # 手機預設折疊側邊欄
)

# --- 行動裝置專用 CSS 樣式微調 ---
st.markdown("""
    <style>
    /* 縮小手機端按鈕邊距與內襯 */
    .stButton>button {
        padding: 0.25rem 0.4rem !important;
        font-size: 0.85rem !important;
        margin-bottom: 2px !important;
    }
    /* 緊湊化 Metric 數據區塊 */
    [data-testid="stMetricValue"] {
        font-size: 1.25rem !important;
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.75rem !important;
    }
    </style>
""", unsafe_allow_html=True)

# ============================
# 密碼驗證機制 ( Password Auth )
# ============================

CORRECT_PASSWORD = "940318"

def check_password():
    if st.session_state.get("password_correct", False):
        return True

    st.title("🔒 系統驗證")
    st.caption("請輸入密碼以存取算牌助手")

    password_input = st.text_input("密碼", type="password", key="password_input")
    
    if st.button("登入", type="primary", use_container_width=True):
        if password_input == CORRECT_PASSWORD:
            st.session_state["password_correct"] = True
            st.rerun()
        else:
            st.error("❌ 密碼錯誤，請重新輸入！")

    return False

if not check_password():
    st.stop()

# ============================
# 靜態常數與狀態初始化
# ============================

CARD_VALUES = {
    "A": -1, "2": 1, "3": 1, "4": 1, "5": 1, "6": 1,
    "7": 0, "8": 0, "9": 0, "10": -1, "J": -1, "Q": -1, "K": -1
}

CARD_ORDER = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
SINGLE_CARD_PER_DECK = 4

default_state = {
    "running_count": 0,
    "cards_seen": 0,
    "history": [],
    "tc_history": [0.0],
    "player_cards": [],
    "dealer_card": "未輸入",
}

for key, value in default_state.items():
    if key not in st.session_state:
        st.session_state[key] = value

# ============================
# 側邊欄與資料運算
# ============================

st.sidebar.title("⚙️ 遊戲設定")
decks = st.sidebar.slider("總牌組數 (Decks)", 1, 8, 6)
unit = st.sidebar.number_input("基本下注單位 (元)", 100, 50000, 100, step=100)

if st.sidebar.button("🔒 登出系統", use_container_width=True):
    st.session_state["password_correct"] = False
    st.rerun()

max_per_card = decks * SINGLE_CARD_PER_DECK
card_counts = {card: st.session_state.history.count(card) for card in CARD_ORDER}

total_cards = decks * 52
remaining_cards = max(0, total_cards - st.session_state.cards_seen)
remaining_decks = max(0.01, remaining_cards / 52)
true_count = st.session_state.running_count / remaining_decks
penetration = min(100.0, (st.session_state.cards_seen / total_cards) * 100)
advantage = -0.5 + (true_count * 0.5)

# ============================
# 核心演算法 Engine
# ============================

def betting_system(tc):
    if tc < 1:
        return 1, "🔴 最小下注"
    elif tc < 2:
        return 2, "🙂 小幅加注"
    elif tc < 3:
        return 4, "🟡 中度加注"
    elif tc < 4:
        return 6, "🟢 大幅加注"
    elif tc < 5:
        return 8, "🔥 強勢下注"
    else:
        return 12, "🔥🔥 最大注碼"

def calculate_hand_value(cards):
    if not cards:
        return 0, False
    value, aces = 0, 0
    for c in cards:
        if c == "A":
            value += 11
            aces += 1
        elif c in ["10", "J", "Q", "K"]:
            value += 10
        else:
            value += int(c)
    while value > 21 and aces:
        value -= 10
        aces -= 1
    return value, (aces > 0)

def get_blackjack_strategy(player_cards, dealer_card, tc):
    if not player_cards or dealer_card == "未輸入":
        return "ℹ️ 請選擇『莊家明牌』與『玩家手牌』"

    value, soft = calculate_hand_value(player_cards)
    dealer_val = 10 if dealer_card in ["10", "J", "Q", "K"] else (11 if dealer_card == "A" else int(dealer_card))
    is_initial_two = (len(player_cards) == 2)

    if value > 21:
        return "💥 爆牌 (Bust)"
    if value == 21 and is_initial_two:
        return "🎉 21點 (Blackjack) → 🛑 停牌"

    # 1. 投降策略
    if is_initial_two:
        if value == 16:
            if dealer_val in [9, 10, 11]:
                return "🏳️ 投降 (Surrender)"
            if dealer_val == 8 and tc >= 4:
                return "🏳️ 投降 【TC ≥ 4】"
        elif value == 15:
            if dealer_val == 10:
                return "🏳️ 投降 (Surrender)" if tc >= 0 else "👉 要牌 (Hit)"
            if dealer_val in [9, 11] and tc >= 2:
                return "🏳️ 投降 【TC ≥ 2】"

    # 2. Illustrious 18
    if value == 16 and dealer_val == 10 and tc >= 0:
        return "🛑 停牌 【TC ≥ 0 改停】"
    if value == 15 and dealer_val == 10 and tc >= 4:
        return "🛑 停牌 【TC ≥ 4 改停】"

    # 3. 分牌
    if is_initial_two and player_cards[0] == player_cards[1]:
        pair = player_cards[0]
        if pair in ["A", "8"]:
            return "✂️ 分牌 (Split)"
        if pair in ["10", "J", "Q", "K"]:
            return "🛑 停牌 (Stand)"
        if pair == "5":
            return "🔥 加倍 (Double)" if dealer_val <= 9 else "👉 要牌 (Hit)"
        if pair == "9":
            return "✂️ 分牌" if dealer_val in [2, 3, 4, 5, 6, 8, 9] else "🛑 停牌"
        if pair in ["2", "3", "7"] and dealer_val <= 7:
            return "✂️ 分牌 (Split)"
        if pair == "6" and dealer_val <= 6:
            return "✂️ 分牌 (Split)"
        if pair == "4" and dealer_val in [5, 6]:
            return "✂️ 分牌 (Split)"

    # 4. 軟牌策略
    if soft:
        if value >= 19:
            if value == 19 and is_initial_two and dealer_val == 6 and tc >= 1:
                return "🔥 加倍 【Soft 19 vs 6】"
            return "🛑 停牌 (Stand)"
        if value == 18:
            if is_initial_two and dealer_val in [2, 3, 4, 5, 6]:
                return "🔥 加倍 (Double)"
            return "🛑 停牌" if dealer_val in [7, 8] else "👉 要牌"
        if value == 17 and is_initial_two and dealer_val in [3, 4, 5, 6]:
            return "🔥 加倍 (Double)"
        if value in [15, 16] and is_initial_two and dealer_val in [4, 5, 6]:
            return "🔥 加倍 (Double)"
        if value in [13, 14] and is_initial_two and dealer_val in [5, 6]:
            return "🔥 加倍 (Double)"
        return "👉 要牌 (Hit)"

    # 5. 硬牌策略
    if value >= 17:
        return "🛑 停牌 (Stand)"
    if value >= 13:
        return "🛑 停牌" if dealer_val <= 6 else "👉 要牌"
    if value == 12:
        return "🛑 停牌" if dealer_val in [4, 5, 6] else "👉 要牌"
    if value == 11:
        return "🔥 加倍 (Double)"
    if value == 10:
        return "🔥 加倍" if dealer_val <= 9 else "👉 要牌"
    if value == 9:
        return "🔥 加倍" if dealer_val in [3, 4, 5, 6] else "👉 要牌"

    return "👉 要牌 (Hit)"

# ============================
# 頁面 UI 渲染
# ============================

st.title("🃏 21點算牌助手")
st.caption(f"Hi-Lo 算牌法 | {decks} 副牌（單張上限：{max_per_card}）")

# --- 數據儀表板（適應手機改為 3x2 佈局） ---
m1, m2, m3 = st.columns(3)
m1.metric("流水數 RC", st.session_state.running_count)
m2.metric("真數 TC", f"{true_count:.2f}")
m3.metric("剩餘 Deck", f"{remaining_decks:.1f}")

m4, m5, m6 = st.columns(3)
m4.metric("已出牌", f"{st.session_state.cards_seen}/{total_cards}")
m5.metric("剩餘張數", remaining_cards)
m6.metric("切牌深度", f"{penetration:.0f}%")

# --- 下注建議 ---
bet_multi, bet_text = betting_system(true_count)

st.success(f"💰 **建議**：{bet_text} | **{bet_multi} 倍** (${bet_multi * unit:,} 元)")

if true_count >= 2:
    st.info("🟢 正期望值區間 (TC ≥ 2)")
if remaining_decks <= 1.5:
    st.error("⚠️ 即將到達切牌線，準備重新洗牌！")

st.divider()

# --- 快捷大局記牌區 (手機友好 4 欄/列) ---
st.subheader("🃏 快速記牌 (點擊次數)")

cols = st.columns(4)
for i, card in enumerate(CARD_ORDER):
    seen_count = card_counts[card]
    is_disabled = seen_count >= max_per_card
    # 精簡標籤，節省手機寬度
    label = f"{card} ({seen_count})"
    
    with cols[i % 4]:
        if st.button(label, key=f"btn_{card}", use_container_width=True, disabled=is_disabled):
            st.session_state.running_count += CARD_VALUES[card]
            st.session_state.cards_seen += 1
            st.session_state.history.append(card)
            
            rem_decks = max(0.01, (total_cards - st.session_state.cards_seen) / 52)
            new_tc = st.session_state.running_count / rem_decks
            st.session_state.tc_history.append(round(new_tc, 2))
            st.rerun()

# --- 撤銷與重置按鈕 ---
col_u1, col_u2 = st.columns(2)
with col_u1:
    if st.button("↩️ 撤銷上一張", use_container_width=True):
        if st.session_state.history:
            last = st.session_state.history.pop()
            st.session_state.running_count -= CARD_VALUES[last]
            st.session_state.cards_seen -= 1
            if len(st.session_state.tc_history) > 1:
                st.session_state.tc_history.pop()
            st.rerun()

with col_u2:
    if st.button("🔄 洗牌重置", type="primary", use_container_width=True):
        st.session_state.running_count = 0
        st.session_state.cards_seen = 0
        st.session_state.history = []
        st.session_state.tc_history = [0.0]
        st.session_state.player_cards = []
        st.session_state.dealer_card = "未輸入"
        st.rerun()

st.divider()

# --- 手牌策略分析區 (簡化尺寸) ---
st.subheader("🎰 手牌策略分析")

# 莊家選擇與手牌資訊
dealer_options = ["未輸入"] + CARD_ORDER
current_dealer = st.session_state.dealer_card
default_dealer_index = dealer_options.index(current_dealer) if current_dealer in dealer_options else 0

dealer = st.selectbox("莊家明牌 (Upcard)", options=dealer_options, index=default_dealer_index)
st.session_state.dealer_card = dealer

# 玩家手牌快速選擇 (改為 5 欄適應手機)
st.write("**加入玩家手牌：**")
p_btn_cols = st.columns(5)
for i, card in enumerate(CARD_ORDER):
    with p_btn_cols[i % 5]:
        if st.button(f"+{card}", key=f"p_add_{card}", use_container_width=True):
            st.session_state.player_cards.append(card)
            st.rerun()

if st.session_state.player_cards:
    cards_display = " ".join([f"`[{c}]`" for c in st.session_state.player_cards])
    st.markdown(f"目前組合：{cards_display}")
    if st.button("🗑️ 清空手牌", key="clear_p_cards", use_container_width=True):
        st.session_state.player_cards = []
        st.rerun()

# 策略分析輸出
strategy = get_blackjack_strategy(
    st.session_state.player_cards, 
    st.session_state.dealer_card, 
    true_count
)

st.info(f"🤖 **AI 建議：** {strategy}")
st.caption(f"預估玩家優勢 (EV): **{advantage:.2f}%**")

st.divider()

# --- True Count 走勢圖 (摺疊呈現，節省手機空間) ---
with st.expander("📈 檢視真數 (True Count) 走勢圖"):
    if len(st.session_state.tc_history) > 1:
        df_tc = pd.DataFrame({
            "出牌張數": list(range(len(st.session_state.tc_history))),
            "真數": st.session_state.tc_history
        })
        fig = px.line(df_tc, x="出牌張數", y="真數", markers=True)
        fig.add_hline(y=2.0, line_dash="dash", line_color="green")
        fig.add_hline(y=0.0, line_dash="dot", line_color="gray")
        fig.update_layout(margin=dict(l=10, r=10, t=20, b=20), height=250)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.caption("點擊上方卡牌按鈕後即可呈現圖表。")

# --- 最近出牌紀錄 (摺疊呈現) ---
with st.expander("📜 檢視最近出牌歷史"):
    if st.session_state.history:
        st.write(" ".join([f"`{x}`" for x in st.session_state.history[-20:]]))
    else:
        st.caption("尚無出牌紀錄")
