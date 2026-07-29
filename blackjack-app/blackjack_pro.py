import streamlit as st
import pandas as pd
import plotly.express as px

# ======================================
# 21點算牌助手 (含密碼保護與圖表分析版)
# ======================================

st.set_page_config(
    page_title="21點算牌助手",
    page_icon="🃏",
    layout="centered"
)

# ============================
# 密碼驗證機制 ( Password Auth )
# ============================

CORRECT_PASSWORD = "940318"

def check_password():
    """回傳 True 代表密碼正確，驗證失敗則顯示輸入框並停止執行"""
    if st.session_state.get("password_correct", False):
        return True

    st.title("🔒 系統驗證")
    st.subheader("請輸入密碼以存取 21 點算牌助手")

    password_input = st.text_input("密碼", type="password", key="password_input")
    
    if st.button("登入", type="primary"):
        if password_input == CORRECT_PASSWORD:
            st.session_state["password_correct"] = True
            st.rerun()
        else:
            st.error("❌ 密碼錯誤，請重新輸入！")

    return False

if not check_password():
    st.stop()

# ============================
# 靜態常數定義
# ============================

CARD_VALUES = {
    "A": -1, "2": 1, "3": 1, "4": 1, "5": 1, "6": 1,
    "7": 0, "8": 0, "9": 0, "10": -1, "J": -1, "Q": -1, "K": -1
}

CARD_ORDER = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
SINGLE_CARD_PER_DECK = 4

# ============================
# Session 狀態初始化
# ============================

default_state = {
    "running_count": 0,
    "cards_seen": 0,
    "history": [],
    "tc_history": [0.0],  # 記錄 True Count 歷史變動
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

if st.sidebar.button("🔒 登出系統"):
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
    """計算建議下注倍數與狀態"""
    if tc < 1:
        return 1, "🔴 最小下注 (保守平注)"
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
    """計算玩家手牌點數與是否為 Soft 手牌"""
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
    """基本策略 + Surrender + 完整 Soft Double + Illustrious 18"""
    if not player_cards or dealer_card == "未輸入":
        return "ℹ️ 請先選擇『莊家明牌』與『玩家手牌』"

    value, soft = calculate_hand_value(player_cards)
    dealer_val = 10 if dealer_card in ["10", "J", "Q", "K"] else (11 if dealer_card == "A" else int(dealer_card))
    is_initial_two = (len(player_cards) == 2)

    if value > 21:
        return "💥 爆牌 (Bust)"
    if value == 21 and is_initial_two:
        return "🎉 21點 (Blackjack) → 🛑 停牌 (Stand)"

    # --- 1. 投降策略 (Surrender) ---
    if is_initial_two:
        if value == 16:
            if dealer_val in [9, 10, 11]:
                return "🏳️ 投降 (Surrender)"
            if dealer_val == 8 and tc >= 4:
                return "🏳️ 投降 (Surrender) 【偏離：TC ≥ 4】"
        elif value == 15:
            if dealer_val == 10:
                return "🏳️ 投降 (Surrender)" if tc >= 0 else "👉 要牌 (Hit)"
            if dealer_val in [9, 11] and tc >= 2:
                return "🏳️ 投降 (Surrender) 【偏離：TC ≥ 2】"

    # --- 2. Illustrious 18 停牌偏離 ---
    if value == 16 and dealer_val == 10 and tc >= 0:
        return "🛑 停牌 (Stand) 【偏離：TC ≥ 0 改停牌】"
    if value == 15 and dealer_val == 10 and tc >= 4:
        return "🛑 停牌 (Stand) 【偏離：TC ≥ 4 改停牌】"

    # --- 3. 對子分牌 (Split) ---
    if is_initial_two and player_cards[0] == player_cards[1]:
        pair = player_cards[0]
        if pair in ["A", "8"]:
            return "✂️ 分牌 (Split)"
        if pair in ["10", "J", "Q", "K"]:
            return "🛑 停牌 (Stand)"
        if pair == "5":
            return "🔥 加倍 (Double)" if dealer_val <= 9 else "👉 要牌 (Hit)"
        if pair == "9":
            return "✂️ 分牌 (Split)" if dealer_val in [2, 3, 4, 5, 6, 8, 9] else "🛑 停牌 (Stand)"
        if pair in ["2", "3", "7"] and dealer_val <= 7:
            return "✂️ 分牌 (Split)"
        if pair == "6" and dealer_val <= 6:
            return "✂️ 分牌 (Split)"
        if pair == "4" and dealer_val in [5, 6]:
            return "✂️ 分牌 (Split)"

    # --- 4. 軟牌策略 (Soft Hand, 含完整 Soft Double) ---
    if soft:
        if value >= 19:
            if value == 19 and is_initial_two and dealer_val == 6 and tc >= 1:
                return "🔥 加倍 (Double) 【偏離：Soft 19 vs 6】"
            return "🛑 停牌 (Stand)"
        
        if value == 18:
            if is_initial_two and dealer_val in [2, 3, 4, 5, 6]:
                return "🔥 加倍 (Double)"
            return "🛑 停牌 (Stand)" if dealer_val in [7, 8] else "👉 要牌 (Hit)"
            
        if value == 17 and is_initial_two and dealer_val in [3, 4, 5, 6]:
            return "🔥 加倍 (Double)"
        if value in [15, 16] and is_initial_two and dealer_val in [4, 5, 6]:
            return "🔥 加倍 (Double)"
        if value in [13, 14] and is_initial_two and dealer_val in [5, 6]:
            return "🔥 加倍 (Double)"
            
        return "👉 要牌 (Hit)"

    # --- 5. 硬牌策略 (Hard Hand) ---
    if value >= 17:
        return "🛑 停牌 (Stand)"
    if value >= 13:
        return "🛑 停牌 (Stand)" if dealer_val <= 6 else "👉 要牌 (Hit)"
    if value == 12:
        return "🛑 停牌 (Stand)" if dealer_val in [4, 5, 6] else "👉 要牌 (Hit)"
    if value == 11:
        return "🔥 加倍 (Double)"
    if value == 10:
        return "🔥 加倍 (Double)" if dealer_val <= 9 else "👉 要牌 (Hit)"
    if value == 9:
        return "🔥 加倍 (Double)" if dealer_val in [3, 4, 5, 6] else "👉 要牌 (Hit)"

    return "👉 要牌 (Hit)"

# ============================
# 頁面 UI 渲染
# ============================

st.title("🃏 21點算牌助手")
st.caption(f"Hi-Lo 算牌法 | 當前模式：{decks} 副牌（單面上限：{max_per_card} 張）")

# --- 儀表板區域 ---
c1, c2, c3 = st.columns(3)
c1.metric("流水數 (Running Count)", st.session_state.running_count)
c2.metric("真數 (True Count)", f"{true_count:.2f}")
c3.metric("剩餘牌組數", f"{remaining_decks:.2f}")

c4, c5, c6 = st.columns(3)
c4.metric("已出牌數", f"{st.session_state.cards_seen} / {total_cards}")
c5.metric("剩餘牌數", remaining_cards)
c6.metric("牌堆切牌深度", f"{penetration:.1f}%")

st.divider()

# --- 下注建議區 ---
bet_multi, bet_text = betting_system(true_count)

st.success(f"""
### 💰 下注策略建議
* **狀態說明**：{bet_text}
* **建議倍數**：{bet_multi} 倍
* **建議金額**：${bet_multi * unit:,} 元
""")

if true_count >= 2:
    st.info("🟢 玩家優勢區間：數學期望值已轉正")
else:
    st.warning("🔴 莊家優勢區間：保持最小注碼")

if remaining_decks <= 1.5:
    st.error("⚠️ 警告：即將到達切牌線 (Cut Card)，準備重新洗牌")

st.divider()

# --- 快捷大局算牌區 ---
st.subheader("🃏 快速點擊記錄已出現牌 (大局記牌)")

cols = st.columns(5)
for i, card in enumerate(CARD_ORDER):
    seen_count = card_counts[card]
    is_disabled = seen_count >= max_per_card
    label = f"{card}\n({seen_count}/{max_per_card})"
    
    with cols[i % 5]:
        if st.button(label, key=f"btn_{card}", use_container_width=True, disabled=is_disabled):
            st.session_state.running_count += CARD_VALUES[card]
            st.session_state.cards_seen += 1
            st.session_state.history.append(card)
            
            # 計算並更新 TC 歷史紀錄
            rem_decks = max(0.01, (total_cards - st.session_state.cards_seen) / 52)
            new_tc = st.session_state.running_count / rem_decks
            st.session_state.tc_history.append(round(new_tc, 2))
            st.rerun()

# --- 重置與撤銷按鈕 ---
col_u1, col_u2 = st.columns(2)
with col_u1:
    if st.button("↩️ 撤銷上一張牌", use_container_width=True):
        if st.session_state.history:
            last = st.session_state.history.pop()
            st.session_state.running_count -= CARD_VALUES[last]
            st.session_state.cards_seen -= 1
            if len(st.session_state.tc_history) > 1:
                st.session_state.tc_history.pop()
            st.rerun()

with col_u2:
    if st.button("🔄 洗牌重置 (Reset)", type="primary", use_container_width=True):
        st.session_state.running_count = 0
        st.session_state.cards_seen = 0
        st.session_state.history = []
        st.session_state.tc_history = [0.0]
        st.session_state.player_cards = []
        st.session_state.dealer_card = "未輸入"
        st.rerun()

st.divider()

# --- 歷史 True Count 圖表 ---
st.subheader("📈 真數 (True Count) 歷史走勢圖")
if len(st.session_state.tc_history) > 1:
    df_tc = pd.DataFrame({
        "出牌張數": list(range(len(st.session_state.tc_history))),
        "真數 (True Count)": st.session_state.tc_history
    })
    fig = px.line(
        df_tc, 
        x="出牌張數", 
        y="真數 (True Count)", 
        title="牌局真數變動趨勢", 
        markers=True
    )
    fig.add_hline(y=2.0, line_dash="dash", line_color="green", annotation_text="優勢區間 (TC≥2)")
    fig.add_hline(y=0.0, line_dash="dot", line_color="gray")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.caption("點擊上方卡牌按鈕後即可呈現真數趨勢圖表。")

st.divider()

# --- 當前手牌策略分析區 ---
st.subheader("🎰 當前手牌策略決策區")

d_col, p_col = st.columns([1, 2])

with d_col:
    dealer_options = ["未輸入"] + CARD_ORDER
    current_dealer = st.session_state.dealer_card
    default_dealer_index = dealer_options.index(current_dealer) if current_dealer in dealer_options else 0

    dealer = st.selectbox(
        "莊家明牌 (Upcard)",
        options=dealer_options,
        index=default_dealer_index
    )
    st.session_state.dealer_card = dealer

with p_col:
    st.write("**玩家手牌 (點擊按鈕快速加入)**")
    
    if st.session_state.player_cards:
        cards_display = " ".join([f"`[{c}]`" for c in st.session_state.player_cards])
        st.markdown(f"目前組合：{cards_display}")
    else:
        st.caption("尚未選擇手牌（請點擊下方按鈕）")

    p_btn_cols = st.columns(7)
    for i, card in enumerate(CARD_ORDER):
        with p_btn_cols[i % 7]:
            if st.button(f"+{card}", key=f"p_add_{card}", use_container_width=True):
                st.session_state.player_cards.append(card)
                st.rerun()

    if st.button("🗑️ 清空玩家手牌", key="clear_p_cards", use_container_width=True):
        st.session_state.player_cards = []
        st.rerun()

# --- 策略分析結果輸出 ---
strategy = get_blackjack_strategy(
    st.session_state.player_cards, 
    st.session_state.dealer_card, 
    true_count
)

st.info(f"🤖 **AI 建議動作：** {strategy}")
st.metric("估算玩家優勢 (EV)", f"{advantage:.2f}%")

st.divider()

# --- 歷史紀錄 ---
st.subheader("📜 最近 20 張出牌紀錄")
if st.session_state.history:
    st.write(" ".join([f"`{x}`" for x in st.session_state.history[-20:]]))
else:
    st.caption("尚無出牌紀錄")