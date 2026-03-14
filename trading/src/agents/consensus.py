"""Multi-LLM consensus graph using LangGraph.

Fan-out: 3 LLMs run in parallel via the unified router.
Fan-in: results feed into bull/bear debate, then synthesizer.

All LLM calls go through the unified LLM router service (services/llm-router)
to ensure consistent cost tracking, circuit breaking, and fallback chains.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx
from loguru import logger

from src.agents.state import ConsensusState

# Configuration
LLM_ROUTER_URL = os.getenv("LLM_ROUTER_URL", "http://localhost:5100")
LLM_TIMEOUT = int(os.getenv("LLM_CONSENSUS_TIMEOUT", "45"))


def _build_probability_prompt(state: ConsensusState) -> str:
    """Build the probability estimation prompt from market state."""
    market = state.get("market", {})
    question = market.get("question", "Unknown market question")
    description = market.get("description", "")
    current_price = market.get("price", "N/A")
    volume = market.get("volume", "N/A")
    end_date = market.get("end_date", "N/A")

    return (
        f"You are a prediction market analyst. Estimate the probability that the following "
        f"event resolves YES.\n\n"
        f"Question: {question}\n"
        f"Description: {description[:500]}\n"
        f"Current market price: {current_price}\n"
        f"24h volume: {volume}\n"
        f"End date: {end_date}\n\n"
        f"Respond ONLY with valid JSON:\n"
        f'{{"probability": <float 0.01-0.99>, "confidence": "<high|medium|low>", '
        f'"reasoning": "<2-3 sentence explanation>"}}'
    )


def _parse_llm_response(raw_text: str, provider_name: str) -> dict:
    """Parse LLM JSON response into estimate dict. Handles markdown fences."""
    try:
        cleaned = re.sub(r"\`\`\`(?:json)?\s*", "", raw_text).strip().rstrip("\`")
        data = json.loads(cleaned)
        prob = float(data.get("probability", 0.5))
        prob = max(0.01, min(0.99, prob))
        confidence = data.get("confidence", "medium")
        if confidence not in ("high", "medium", "low"):
            confidence = "medium"
        reasoning = data.get("reasoning", f"{provider_name} analysis")
        return {
            "probability": prob,
            "confidence": confidence,
            "reasoning": reasoning,
        }
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        logger.warning("Failed to parse %s response: %s — raw: %s", provider_name, e, raw_text[:200])
        return {
            "probability": 0.5,
            "confidence": "low",
            "reasoning": f"{provider_name} response could not be parsed",
        }


async def _call_router(prompt: str, tier: str = "deep", preferred_provider: str | None = None) -> str:
    """Call the unified LLM router and return the response text."""
    payload: dict[str, Any] = {
        "messages": [{"role": "user", "content": prompt}],
        "tier": tier,
        "temperature": 0.2,
        "max_tokens": 300,
    }
    if preferred_provider:
        payload["preferred_provider"] = preferred_provider

    async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as client:
        resp = await client.post(f"{LLM_ROUTER_URL}/v1/chat/completions", json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()


async def call_claude_node(state: ConsensusState) -> dict:
    """Claude analyst node — calls Claude via the unified router."""
    prompt = _build_probability_prompt(state)
    try:
        raw = await _call_router(prompt, tier="deep", preferred_provider="anthropic")
        estimate = _parse_llm_response(raw, "Claude")
    except Exception as e:
        logger.error("Claude node failed: %s", e)
        estimate = {"probability": 0.5, "confidence": "low", "reasoning": f"Claude call failed: {e}"}

    return {
        "claude_estimate": estimate,
        "messages": [{"role": "claude", "content": f"Analysis: p={estimate['probability']:.3f}"}],
    }


async def call_gemini_node(state: ConsensusState) -> dict:
    """Gemini analyst node — calls Gemini via the unified router."""
    prompt = _build_probability_prompt(state)
    try:
        raw = await _call_router(prompt, tier="deep", preferred_provider="google")
        estimate = _parse_llm_response(raw, "Gemini")
    except Exception as e:
        logger.error("Gemini node failed: %s", e)
        estimate = {"probability": 0.5, "confidence": "low", "reasoning": f"Gemini call failed: {e}"}

    return {
        "gemini_estimate": estimate,
        "messages": [{"role": "gemini", "content": f"Analysis: p={estimate['probability']:.3f}"}],
    }


async def call_gpt_node(state: ConsensusState) -> dict:
    """GPT analyst node — calls GPT via the unified router."""
    prompt = _build_probability_prompt(state)
    try:
        raw = await _call_router(prompt, tier="balanced", preferred_provider="openrouter")
        estimate = _parse_llm_response(raw, "GPT")
    except Exception as e:
        logger.error("GPT node failed: %s", e)
        estimate = {"probability": 0.5, "confidence": "low", "reasoning": f"GPT call failed: {e}"}

    return {
        "gpt_estimate": estimate,
        "messages": [{"role": "gpt", "content": f"Analysis: p={estimate['probability']:.3f}"}],
    }



async def call_nemotron_node(state: ConsensusState) -> dict:
    """Nemotron analyst - agentic reasoning via NVIDIA NIM."""
    prompt = _build_probability_prompt(state)
    try:
        raw = await _call_router(prompt, tier="deep", preferred_provider="nvidia_nim")
        estimate = _parse_llm_response(raw, "Nemotron")
    except Exception as e:
        logger.error("Nemotron node failed: %s", e)
        estimate = {"probability": 0.5, "confidence": "low",
                    "reasoning": f"Nemotron call failed: {e}"}
    return {
        "nemotron_estimate": estimate,
        "messages": [{"role": "nemotron",
                      "content": "Analysis: p=%.3f" % estimate["probability"]}],
    }

async def argue_bull_case(state: ConsensusState) -> dict:
    """Bull researcher — argues for higher probability using LLM analysis."""
    estimates = []
    reasonings = []
    for key in ["claude_estimate", "gemini_estimate", "gpt_estimate", "nemotron_estimate"]:
        est = state.get(key)
        if est and isinstance(est, dict):
            estimates.append(est.get("probability", 0.5))
            reasonings.append(est.get("reasoning", ""))

    avg = sum(estimates) / len(estimates) if estimates else 0.5
    context = "; ".join(r for r in reasonings if r)

    try:
        prompt = (
            f"You are a bull-case analyst. Given these analyst estimates (avg: {avg:.3f}) "
            f"and their reasoning: {context[:500]}\n\n"
            f"Make the strongest case for why the probability should be HIGHER than {avg:.3f}. "
            f"Be specific and cite data. Keep it to 2-3 sentences."
        )
        raw = await _call_router(prompt, tier="fast")
        bull_case = raw[:500]
    except Exception as e:
        logger.warning("Bull case LLM failed: %s", e)
        bull_case = f"Bull case: factors supporting higher probability (avg estimate: {avg:.3f})"

    return {
        "bull_case": bull_case,
        "messages": [{"role": "bull", "content": "Bull case argued"}],
    }


async def argue_bear_case(state: ConsensusState) -> dict:
    """Bear researcher — argues for lower probability using LLM analysis."""
    estimates = []
    reasonings = []
    for key in ["claude_estimate", "gemini_estimate", "gpt_estimate", "nemotron_estimate"]:
        est = state.get(key)
        if est and isinstance(est, dict):
            estimates.append(est.get("probability", 0.5))
            reasonings.append(est.get("reasoning", ""))

    avg = sum(estimates) / len(estimates) if estimates else 0.5
    context = "; ".join(r for r in reasonings if r)

    try:
        prompt = (
            f"You are a bear-case analyst. Given these analyst estimates (avg: {avg:.3f}) "
            f"and their reasoning: {context[:500]}\n\n"
            f"Make the strongest case for why the probability should be LOWER than {avg:.3f}. "
            f"Be specific and cite risks/uncertainties. Keep it to 2-3 sentences."
        )
        raw = await _call_router(prompt, tier="fast")
        bear_case = raw[:500]
    except Exception as e:
        logger.warning("Bear case LLM failed: %s", e)
        bear_case = f"Bear case: factors supporting lower probability (avg: {avg:.3f})"

    return {
        "bear_case": bear_case,
        "messages": [{"role": "bear", "content": "Bear case argued"}],
    }


async def synthesize_consensus(state: ConsensusState) -> dict:
    """Synthesizer — produces final consensus from all inputs."""
    estimates = []
    for key in ["claude_estimate", "gemini_estimate", "gpt_estimate", "nemotron_estimate"]:
        est = state.get(key)
        if est and isinstance(est, dict):
            estimates.append(est.get("probability", 0.5))

    if estimates:
        consensus = sum(estimates) / len(estimates)
        spread = max(estimates) - min(estimates)
    else:
        consensus = 0.5
        spread = 0.0

    confidence = "high" if spread < 0.10 else "medium" if spread < 0.20 else "low"

    return {
        "consensus_probability": max(0.01, min(0.99, consensus)),
        "consensus_confidence": confidence,
        "messages": [
            {
                "role": "synthesizer",
                "content": f"Consensus: {consensus:.3f} ({confidence})",
            }
        ],
    }



async def nemotron_arbitrate(state: ConsensusState) -> dict:
    """Nemotron meta-arbitrator: resolves split votes using full context.
    
    When analysts disagree (no 3/4 majority), Nemotron reviews ALL estimates
    with its 1M context window and makes the final call with structured reasoning.
    """
    estimates = {}
    for key in ["claude_estimate", "gemini_estimate", "gpt_estimate", "nemotron_estimate"]:
        if key in state and state[key]:
            estimates[key] = state[key]
    
    # Check if there is a clear majority (3+ agree on direction)
    bullish = sum(1 for e in estimates.values() if e.get("probability", 0.5) > 0.6)
    bearish = sum(1 for e in estimates.values() if e.get("probability", 0.5) < 0.4)
    
    if bullish >= 3 or bearish >= 3:
        # Clear consensus - no arbitration needed
        return {"messages": [{"role": "arbitrator", "content": "Clear consensus, no arbitration needed"}]}
   p y
t h o n 3#  <S<p l'iEtO Fv'o
tfe= o-p eNne(m'ottrraodni nagr/bsirtcr/aatgeesn twsi/tcho nfsuelnls ucso.nptye'x)t;
  c = f .prreoamdp(t) ;=  ff."c"l"oYsoeu( )a
r
e#  tAhded  caornbsietnrsautso ra rfbuintcrtaitoonr  bfeofro rae  mbuulitlid-_LcLoMn sternasduisn_gg rsaypsht
eamr.b
=T'h'e' 
aansaylnycs tdse fh anveem oStPrLoInT_ aornb itthriast et(rsatdaet.e :R eCvoineswe nasluls Setsattiem)a t-e>s  daincdt :m
a k e   t"h"e" Nfeimnoatlr ocna lmle.t
a
-AaNrAbLiYtSrTa tEoSrT:I MrAeTsEoSl:v
e{sc hsrp(l1i0t) .vjootiens( fu"s-i n{gk }f:u lplr ocboanbtielxitt.y
= { v . g
e t ( ' pWrhoebna bainlailtyys't,s  'dNi/sAa'g)r}e,e  c(onnof i3d/e4n cmea=j{ovr.igteyt)(,' cNoenmfoitdreonnc er'e,v i'eNw/sA 'A)L}L,  ersetaismoantiensg
= { v . gweitt(h' rietass o1nMi ncgo'n,t e'xNt/ Aw'i)n}d"o wf oarn dk ,m avk eisn  tehset ifmiantaels .ciatlelm sw(i)t)h} 
s
tMrAuRcKtEuTr eCdO NrTeEaXsTo:n
i{nsgt.a
t e . g e"t"("'
m a r k eets_tdiamtaat'e,s  '=N o{ }a
d d i t ifoonra lk emya rikne t[ "dcaltaau'd)e}_
e
sYtOiUmRa tTeA"S,K :"
g1e.m iIndie_netsitfiym awthei"c,h  "agnpatl_yesstt ihmaast et"h,e  "sntermoontgreosnt_ ersetaismoantien"g]
:2
.   I d e n t i fiyf  lkoegyi cianl  sftlaatwes  ainnd  dsitsasteen[tkienyg] :o
p i n i o n s     
 3 .  ePsrtoivmiadtee sy[okuery ]F I=N AsLt aptreo[bkaebyi]l
i t y   (
0 - 1 )  #a nCdh eccokn fiifd etnhceer e( liosw /am ecdlieuamr/ hmiagjho)r
i4t.y  E(x3p+l aaignr eyeo uorn  adribrietcrtaitoino)n
  r e a sbounlilnigs hi n=  2s-u3m (s1e nftoern cee si
n
 Reesstpiomnadt eass. vJaSlOuNe:s ({){ "iffi nea.lg_eptr(o"bparboiblaibtiyl"i:t y0".,X ,0 ."5f)i n>a l0_.c6o)n
f i d e nbceea"r:i s"h. .=. "s,u m"(a1r bfiotrr aet iionn _ersetaismoantiensg."v:a l"u.e.s.("),  i"fs ter.ognegte(s"tp_raonbaalbyislti"t:y "",. .0.."5})} "<" "0
.
4 ) 
    t r y
: 
      i f   b u lrlaiws h=  >a=w a3i to r_ cbaelalr_irsohu t>e=r (3p:r
o m p t ,   t i e#r =C"ldeeaerp "c,o npsreenfseursr e-d _npor oavribdietrr=a"tnivoind inae_endiemd"
) 
              r eitmupronr t{ "jmseosns
a g e s " :   [ {r"ersoullet" :=  "jasrobni.tlroaatdosr("r,a w")c oinft einsti"n:s t"aCnlceea(rr acwo,n ssetnrs)u se,l sneo  raarwb
i t r a t i o n  rneeteudrend "{}
] } 
         
         #" aSrpbliittr avtoitoen _-r eNseumlott"r:o nr easrublitt,r
a t e s   w i t h   f u l"lm ecsosnatgeexst"
:   [ { "prroolmep"t:  =" afr"b"i"tYroaut oarr"e, 
t h e   c o n s e n s u s   a r b i t r a t o r   f o"rc oan tmeunltt"i:- LfL"MA rtbriatdriantgi osny:s tpe=m{.r
eTshuel ta.ngaelty(s'tfsi nhaalv_ep rSoPbLaIbTi loint yt'h,i s0 .t5r)a}d,e .{ rReesvuiletw. gaeltl( 'easrtbiimtartaetsi oann_dr emaaskoen itnhge' ,f i'n'a)l} "c}a]l,l
. 
 
 A N A L Y S}T
  E S T IeMxAcTeEpSt: 
E{xccherp(t1i0o)n. jaosi ne(:f
" -   { k } :   plroogbgaebri.leirtryo=r{(v".Ngeemto(t'rporno baarbbiiltirtayt'i,o n' Nf/aAi'l)e}d,:  c%osn"f,i dee)n
c e = { v . g e tr(e'tcuornnf i{d
e n c e ' ,   ' N / A ' )"}a,r brietarsaotniionng_=r{evs.uglett"(:' r{e"afsionnailn_gp'r,o b'aNb/iAl'i)t}y"" :f o0r. 5k,,  "vf iinna le_sctoinmfaitdeesn.ciet"e:m s"(l)o)w}"
,

M A R K E T   C O N T E X T : 
 { s t a t e . g e t ( ' m a r k e t _ d"aatrab'i,t r'aNtoi oand_drietaisoonnailn gm"a:r kfe"tA rdbaittar'a)t}i
o
nY OfUaRi lTeAdS:K :{
e1}." }I,d
e n t i f y   w h i c h  "amneaslsyasgte sh"a:s  [t{h"er oslter"o:n g"easrtb irteraastoonri"n,g 
"2c.o nItdeenntt"i:f yf "lAorgbiictarla tfiloanw sf aiinl eddi:s s{een}t"i}n]g, 
o p i n i o n s  } 


3'.' 'P
r
oivfi d'en eymooutrr oFnI_NaArLb iptrroabtaeb'i lniotty  i(n0 -c1:)
  a n d  cc o=n fci.dreenpclea c(el(o'wd/emfe dbiuuiml/dh_icgohn)s
e4n.s uEsx_pglraaipnh 'y,o uarr ba r+b i'tdreaft ibouni lrde_acsoonnsienngs uisn_ g2r-a3p hs'e)n
t e n c efs=
o
pReens(p'otnrda daisn gJ/SsOrNc:/ a{g{e"nftisn/aclo_npsreonbsaubsi.lpiyt'y,"':w '0).;X ,f ."wfriintael(_cc)o;n ffi.dcelnocsee"(:) 
" . . . "p,r i"natr(b'iOtKr-aatriboint_rraetaosro'n)i
negl"s:e :"
. . . " ,p r"isnttr(o'nSgKeIsPt-_aarnbailtyrsatt"o:r '").
.E.O"F}
}"""

    try:
        raw = await _call_router(prompt, tier="deep", preferred_provider="nvidia_nim")
        import json
        result = json.loads(raw) if isinstance(raw, str) else raw
        return {
            "arbitration_result": result,
            "messages": [{"role": "arbitrator",
                          "content": f"Arbitration: p={result.get('final_probability', 0.5)}, {result.get('arbitration_reasoning', '')}"}],
        }
    except Exception as e:
        logger.error("Nemotron arbitration failed: %s", e)
        return {
            "arbitration_result": {"final_probability": 0.5, "final_confidence": "low",
                                   "arbitration_reasoning": f"Arbitration failed: {e}"},
            "messages": [{"role": "arbitrator", "content": f"Arbitration failed: {e}"}],
        }

def build_consensus_graph() -> Any:
    """Build the LangGraph consensus workflow.

    Returns the compiled graph, or None if langgraph is not available.
    """
    try:
        from langgraph.graph import END, START, StateGraph

        workflow = StateGraph(ConsensusState)

        workflow.add_node("claude_analyst", call_claude_node)
        workflow.add_node("gemini_analyst", call_gemini_node)
        workflow.add_node("gpt_analyst", call_gpt_node)
        workflow.add_node("nemotron_analyst", call_nemotron_node)
        workflow.add_node("bull_researcher", argue_bull_case)
        workflow.add_node("bear_researcher", argue_bear_case)
        workflow.add_node("synthesizer", synthesize_consensus)

        # Fan-out: all 3 analysts run from START
        workflow.add_edge(START, "claude_analyst")
        workflow.add_edge(START, "gemini_analyst")
        workflow.add_edge(START, "gpt_analyst")
        workflow.add_edge(START, "nemotron_analyst")

        # Fan-in: all 3 -> bull -> bear -> synthesizer
        workflow.add_edge("claude_analyst", "bull_researcher")
        workflow.add_edge("gemini_analyst", "bull_researcher")
        workflow.add_edge("gpt_analyst", "bull_researcher")
        workflow.add_edge("nemotron_analyst", "bull_researcher")
        workflow.add_edge("bull_researcher", "bear_researcher")
        workflow.add_edge("bear_researcher", "synthesizer")
        workflow.add_node("arbitrator", nemotron_arbitrate)
        workflow.add_edge("synthesizer", "arbitrator")
        workflow.add_edge("arbitrator", END)

        graph = workflow.compile()
        logger.info("LangGraph consensus graph compiled successfully")
        return graph

    except ImportError:
        logger.warning("langgraph not installed — consensus graph unavailable")
        return None
