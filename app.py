
import streamlit as st
import pandas as pd
import math
import os
from dotenv import load_dotenv
from supabase import create_client
from datetime import datetime

load_dotenv()

st.set_page_config(page_title="Scanner Cashback Online", page_icon="⚽", layout="wide")

st.markdown("""
<style>
.block-container {padding-top: 1rem; padding-bottom: 2rem;}
h1,h2,h3 {font-weight: 850;}
.result-card {
  border: 2px solid rgba(45, 230, 160, .65);
  background: linear-gradient(180deg, rgba(45,230,160,.13), rgba(12,18,35,.96));
  border-radius: 18px; padding: 1rem 1.1rem; margin-bottom: .8rem;
}
.bet-card {
  border: 1px solid rgba(255,255,255,.13); background: rgba(18,26,45,.92);
  border-radius: 18px; padding: 1rem; min-height: 210px;
}
.bet-card-r7 {
  border: 2px solid rgba(255, 210, 80, .70);
  background: linear-gradient(180deg, rgba(255,210,80,.12), rgba(18,26,45,.92));
  border-radius: 18px; padding: 1rem; min-height: 210px;
}
.house {font-size:.82rem;text-transform:uppercase;letter-spacing:.06em;opacity:.75;font-weight:800;}
.market {font-size:1.5rem;font-weight:900;margin-top:.2rem;}
.money {font-size:1.65rem;font-weight:950;margin:.25rem 0;}
.sub {opacity:.78;font-size:.92rem;}
.badge {
  display:inline-block;padding:.28rem .58rem;border-radius:999px;
  border:1px solid rgba(255,255,255,.18);background:rgba(255,255,255,.07);
  font-size:.78rem;font-weight:750;margin-right:.25rem;margin-bottom:.25rem;
}
.warn {border-left:4px solid #ffd166;padding:.75rem 1rem;background:rgba(255,209,102,.12);border-radius:12px;margin:.75rem 0;}
.ok {border-left:4px solid #3ee6a2;padding:.75rem 1rem;background:rgba(62,230,162,.10);border-radius:12px;margin:.75rem 0;}
</style>
""", unsafe_allow_html=True)

def get_secret(name):
    # Streamlit Cloud: st.secrets
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    # Local: env
    return os.getenv(name)

SUPABASE_URL = get_secret("SUPABASE_URL")
SUPABASE_ANON_KEY = get_secret("SUPABASE_ANON_KEY")

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    st.error("Configure SUPABASE_URL e SUPABASE_ANON_KEY nos Secrets do Streamlit Cloud.")
    st.stop()

supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

@st.cache_data(ttl=20)
def load_odds():
    res = (
        supabase.table("odds_betao")
        .select("*")
        .order("capturado_em", desc=True)
        .limit(3000)
        .execute()
    )
    return pd.DataFrame(res.data)

def brl(x):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "-"
    return f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def pct(x):
    return f"{x:.2f}%".replace(".", ",")

def parse_bool(v):
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in ["true","1","sim","yes","y"]

def ceil_step(x, step=0.01):
    return math.ceil((x - 1e-12) / step) * step if step > 0 else x

def weekly_cashback_loser(stake, rate=0.10, cap=250.0, min_loss=20.0):
    return min(stake * rate, cap) if stake >= min_loss else 0.0

def brasileirao_bonus(stake, is_brasileirao, odd, rate=0.03, cap=100.0, min_stake=50.0, min_odd=1.5):
    if not is_brasileirao or stake < min_stake or odd < min_odd:
        return 0.0
    return min(stake * rate, cap)

def eval_scenario(stakes, odds, winner_idx, is_brasileirao, fb_value, weekly_rate, weekly_cap, br_rate, br_cap):
    total = sum(stakes)
    payout = stakes[winner_idx] * odds[winner_idx]
    immediate = payout - total

    weekly_fbs, br_fbs = [], []
    for i, (s, o) in enumerate(zip(stakes, odds)):
        weekly_fbs.append(0.0 if i == winner_idx else weekly_cashback_loser(s, weekly_rate, weekly_cap))
        br_fbs.append(brasileirao_bonus(s, is_brasileirao, o, br_rate, br_cap))

    weekly_total = sum(weekly_fbs)
    br_total = sum(br_fbs)
    fb_real = (weekly_total + br_total) * fb_value
    return {
        "payout": payout,
        "immediate": immediate,
        "weekly_fb_total": weekly_total,
        "br_fb_total": br_total,
        "fb_real": fb_real,
        "final": immediate + fb_real,
        "weekly_fb_betao": weekly_fbs[0],
        "weekly_fb_r7": weekly_fbs[1],
        "weekly_fb_7games": weekly_fbs[2],
        "br_fb_betao": br_fbs[0],
        "br_fb_r7": br_fbs[1],
        "br_fb_7games": br_fbs[2],
    }

def build_candidate(stakes, odds, is_brasileirao, fb_value, weekly_rate, weekly_cap, br_rate, br_cap, origin):
    scenarios = [
        eval_scenario(stakes, odds, 0, is_brasileirao, fb_value, weekly_rate, weekly_cap, br_rate, br_cap),
        eval_scenario(stakes, odds, 1, is_brasileirao, fb_value, weekly_rate, weekly_cap, br_rate, br_cap),
        eval_scenario(stakes, odds, 2, is_brasileirao, fb_value, weekly_rate, weekly_cap, br_rate, br_cap),
    ]
    immediates = [s["immediate"] for s in scenarios]
    finals = [s["final"] for s in scenarios]
    total = sum(stakes)

    return {
        "stake_1": stakes[0],
        "stake_x": stakes[1],
        "stake_2": stakes[2],
        "total_staked": total,
        "payout_1": stakes[0]*odds[0],
        "payout_x": stakes[1]*odds[1],
        "payout_2": stakes[2]*odds[2],
        "worst_immediate": min(immediates),
        "avg_immediate": sum(immediates)/3,
        "worst_final": min(finals),
        "avg_final": sum(finals)/3,
        "roi_worst_final": min(finals) / total * 100 if total else 0,
        "roi_worst_immediate": min(immediates) / total * 100 if total else 0,
        "s1": scenarios[0],
        "sx": scenarios[1],
        "s2": scenarios[2],
        "origin": origin,
    }

def better_candidate(a, b):
    if b is None:
        return True
    if a["worst_immediate"] > b["worst_immediate"] + 0.005:
        return True
    if abs(a["worst_immediate"] - b["worst_immediate"]) <= 0.005:
        if a["worst_final"] > b["worst_final"] + 0.005:
            return True
        if abs(a["worst_final"] - b["worst_final"]) <= 0.005 and a["total_staked"] < b["total_staked"] - 0.005:
            return True
    return False

def optimize(odds, is_brasileirao, min_stake_each, fb_value, weekly_rate, weekly_cap, br_rate, br_cap, step=0.01, allow_extra=False, max_extra_pct=0.05):
    odds = [float(x) for x in odds]
    target_min = max(min_stake_each * o for o in odds)
    base_stakes = [ceil_step(max(min_stake_each, target_min / o), step) for o in odds]
    best = build_candidate(base_stakes, odds, is_brasileirao, fb_value, weekly_rate, weekly_cap, br_rate, br_cap, "base")

    if not allow_extra or max_extra_pct <= 0:
        return best

    payout_step = max(0.50, step * 100)
    target = target_min + payout_step
    target_max = target_min * (1 + max_extra_pct)

    while target <= target_max + 1e-9:
        stakes = [ceil_step(max(min_stake_each, target / o), step) for o in odds]
        cand = build_candidate(stakes, odds, is_brasileirao, fb_value, weekly_rate, weekly_cap, br_rate, br_cap, "extra")
        if better_candidate(cand, best):
            best = cand
        target += payout_step

    return best

def calculate(df, min_stake_each, fb_value, weekly_rate, weekly_cap, br_rate, br_cap, step, allow_extra, max_extra_pct):
    rows = []
    for _, r in df.iterrows():
        try:
            res = optimize(
                [r["odd_1"], r["odd_x"], r["odd_2"]],
                parse_bool(r["is_brasileirao"]),
                min_stake_each, fb_value, weekly_rate, weekly_cap, br_rate, br_cap,
                step, allow_extra, max_extra_pct
            )
            rows.append({
                "source": r.get("source",""),
                "liga": r.get("liga",""),
                "data": r.get("data",""),
                "horario": r.get("horario",""),
                "jogo": r.get("jogo",""),
                "is_brasileirao": parse_bool(r.get("is_brasileirao", False)),
                "odd_1": float(r["odd_1"]),
                "odd_x": float(r["odd_x"]),
                "odd_2": float(r["odd_2"]),
                "capturado_em": r.get("capturado_em",""),
                **res
            })
        except Exception:
            pass

    out = pd.DataFrame(rows)
    if len(out):
        out = out.sort_values(["worst_immediate", "worst_final", "total_staked"], ascending=[False, False, True]).reset_index(drop=True)
        out.insert(0, "ranking", range(1, len(out)+1))
    return out

st.markdown("# ⚽ Scanner Cashback Online")
st.markdown("Odds vindo do **Supabase**, atualizadas pelo scraper rodando no seu PC.")

df_raw = load_odds()

if df_raw.empty:
    st.warning("Nenhuma odd encontrada no Supabase ainda. Rode o scraper no seu PC.")
    st.stop()

for c in ["odd_1","odd_x","odd_2"]:
    df_raw[c] = pd.to_numeric(df_raw[c], errors="coerce")
df_raw = df_raw.dropna(subset=["odd_1","odd_x","odd_2"])

with st.sidebar:
    st.header("Filtros")
    sources = sorted([x for x in df_raw["source"].dropna().unique()])
    ligas = sorted([x for x in df_raw["liga"].dropna().unique()])

    source_sel = st.multiselect("Fonte", sources, default=sources)
    liga_sel = st.multiselect("Liga", ligas, default=ligas)
    filtro_brasileirao = st.selectbox("Brasileirão", ["Todos", "Apenas Série A", "Apenas qualquer Brasileirão", "Excluir Brasileirão"])

    min_odd = st.number_input("Odd mínima", min_value=1.0, value=1.30, step=0.05)
    busca = st.text_input("Buscar jogo/time")

    st.header("Configuração de cálculo")
    min_stake_each = st.number_input("Mínimo por plataforma", min_value=1.0, value=2500.0, step=100.0)
    fb_value = st.slider("Valor real estimado da freebet", 0.0, 1.0, 0.70, 0.05)
    step = st.selectbox("Arredondar stake para", [0.01, 0.10, 1.0, 5.0, 10.0], index=0)

    allow_extra = st.checkbox("Permitir aumentar stake extra", value=False)
    max_extra_pct = st.slider("Se ativado, aumentar no máximo", 0.0, 0.30, 0.05, 0.01)

    weekly_rate = st.number_input("Cashback semanal (%)", 0.0, 100.0, 10.0, 0.5) / 100
    weekly_cap = st.number_input("Teto semanal por casa", 0.0, 10000.0, 250.0, 10.0)
    br_rate = st.number_input("Bônus Brasileirão diário (%)", 0.0, 100.0, 3.0, 0.5) / 100
    br_cap = st.number_input("Teto diário Brasileirão por casa", 0.0, 10000.0, 100.0, 10.0)

df = df_raw.copy()

if source_sel:
    df = df[df["source"].isin(source_sel)]
if liga_sel:
    df = df[df["liga"].isin(liga_sel)]

if filtro_brasileirao == "Apenas Série A":
    df = df[df["liga"].astype(str).str.contains("Brasileirão Série A", case=False, na=False)]
elif filtro_brasileirao == "Apenas qualquer Brasileirão":
    df = df[df["liga"].astype(str).str.contains("Brasileirão", case=False, na=False)]
elif filtro_brasileirao == "Excluir Brasileirão":
    df = df[~df["liga"].astype(str).str.contains("Brasileirão", case=False, na=False)]

df = df[(df["odd_1"] >= min_odd) & (df["odd_x"] >= min_odd) & (df["odd_2"] >= min_odd)]

if busca.strip():
    df = df[df["jogo"].astype(str).str.contains(busca.strip(), case=False, na=False)]

st.markdown(
    f"<span class='badge'>Odds no banco: {len(df_raw)}</span>"
    f"<span class='badge'>Após filtros: {len(df)}</span>",
    unsafe_allow_html=True
)

if df.empty:
    st.warning("Nenhum jogo após os filtros.")
    st.stop()

result = calculate(df, min_stake_each, fb_value, weekly_rate, weekly_cap, br_rate, br_cap, step, allow_extra, max_extra_pct)

if result.empty:
    st.warning("Nenhum jogo válido para cálculo.")
    st.stop()

best = result.iloc[0]

st.markdown("## ✅ Melhor combinação agora")
st.markdown(f"""
<div class="result-card">
  <div style="font-size:1.25rem;font-weight:900;">#{int(best['ranking'])} — {best['jogo']}</div>
  <div style="margin-top:.35rem;">
    <span class="badge">{best['source']}</span>
    <span class="badge">{best['liga']}</span>
    <span class="badge">{'Brasileirão: SIM' if best['is_brasileirao'] else 'Brasileirão: NÃO'}</span>
    <span class="badge">Total apostado: {brl(best['total_staked'])}</span>
  </div>
</div>
""", unsafe_allow_html=True)

m1, m2, m3, m4 = st.columns(4)
m1.metric("Pior perda imediata", brl(best["worst_immediate"]))
m2.metric("Pior cenário final", brl(best["worst_final"]))
m3.metric("Média final", brl(best["avg_final"]))
m4.metric("ROI pior cenário", pct(best["roi_worst_final"]))

st.markdown("## 🎯 Aposte exatamente assim")
stake_r7 = float(best["stake_x"])
r7_ticket = stake_r7 / 3
c1, c2, c3 = st.columns(3)

with c1:
    st.markdown(f"""<div class="bet-card"><div class="house">Betão</div><div class="market">Vitória Time 1</div><div class="money">{brl(best['stake_1'])}</div><div class="sub">Odd {best['odd_1']:.2f}</div><div class="sub">Faça 1 aposta simples.</div><div class="sub">Retorno se bater: <b>{brl(best['payout_1'])}</b></div></div>""", unsafe_allow_html=True)
with c2:
    st.markdown(f"""<div class="bet-card-r7"><div class="house">R7 — dividir em 3 apostas</div><div class="market">Empate</div><div class="money">{brl(stake_r7)}</div><div class="sub">Odd {best['odd_x']:.2f}</div><div class="sub"><b>Faça 3 apostas de {brl(r7_ticket)}</b></div><div class="sub">Retorno total se bater: <b>{brl(best['payout_x'])}</b></div></div>""", unsafe_allow_html=True)
with c3:
    st.markdown(f"""<div class="bet-card"><div class="house">7Games</div><div class="market">Vitória Time 2</div><div class="money">{brl(best['stake_2'])}</div><div class="sub">Odd {best['odd_2']:.2f}</div><div class="sub">Faça 1 aposta simples.</div><div class="sub">Retorno se bater: <b>{brl(best['payout_2'])}</b></div></div>""", unsafe_allow_html=True)

st.markdown("## 📊 Cenários possíveis")
scenario_rows = []
for key, label in [("s1","Se der Time 1"),("sx","Se der Empate"),("s2","Se der Time 2")]:
    s = best[key]
    scenario_rows.append({
        "Cenário": label,
        "Retorno da casa vencedora": s["payout"],
        "Resultado imediato": s["immediate"],
        "Freebet semanal nominal": s["weekly_fb_total"],
        "Freebet Brasileirão nominal": s["br_fb_total"],
        "Valor real estimado das freebets": s["fb_real"],
        "Resultado final estimado": s["final"],
    })

sc_show = pd.DataFrame(scenario_rows)
for c in sc_show.columns:
    if c != "Cenário":
        sc_show[c] = sc_show[c].map(brl)
st.dataframe(sc_show, hide_index=True, use_container_width=True)

st.markdown("---")
st.markdown("## 🏆 Ranking dos melhores jogos")
rank = result.copy()
rank["Apostar Betão/1"] = rank["stake_1"].map(brl)
rank["Apostar R7/X total"] = rank["stake_x"].map(brl)
rank["R7: 3 apostas de"] = (rank["stake_x"]/3).map(brl)
rank["Apostar 7Games/2"] = rank["stake_2"].map(brl)
rank["Total apostado"] = rank["total_staked"].map(brl)
rank["Pior perda imediata"] = rank["worst_immediate"].map(brl)
rank["Pior cenário final"] = rank["worst_final"].map(brl)
rank["ROI pior cenário"] = rank["roi_worst_final"].map(pct)

rank_show = rank[[
    "ranking","source","liga","data","horario","jogo","is_brasileirao",
    "odd_1","odd_x","odd_2",
    "Apostar Betão/1","Apostar R7/X total","R7: 3 apostas de","Apostar 7Games/2",
    "Total apostado","Pior perda imediata","Pior cenário final","ROI pior cenário","capturado_em"
]].rename(columns={
    "ranking":"#",
    "source":"Fonte",
    "liga":"Liga",
    "data":"Data",
    "horario":"Hora",
    "jogo":"Jogo",
    "is_brasileirao":"Brasileirão",
    "odd_1":"Odd 1",
    "odd_x":"Odd X",
    "odd_2":"Odd 2",
    "capturado_em":"Atualizado em",
})

st.dataframe(rank_show, hide_index=True, use_container_width=True, height=560)

csv_out = result.to_csv(index=False).encode("utf-8-sig")
st.download_button("Baixar ranking CSV", csv_out, "ranking_cashback_online.csv", "text/csv")
