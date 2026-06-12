# 배포 가이드 (무료: Vercel + Render)

프론트엔드(정적 SPA)는 Vercel에, 백엔드(FastAPI)는 Render에 올리는 무료 구성입니다.

> ⚠️ **"BAR에서 실행"(`/launch`)은 배포본에서 동작하지 않습니다.** 그 기능은 백엔드가 도는
> 머신의 데스크톱에서 `spring.exe`를 띄우는 것이라, 화면도 BAR도 없는 클라우드 서버에선
> 불가능합니다. 배포본에서는 자동으로 "launcher not found"로 안전하게 실패하고, 브라우저
> 근사 플레이백(SimPlayback)은 정상 동작합니다.
>
> ⚠️ **호스팅은 무료지만 LLM 호출은 본인 OpenAI 키로 과금됩니다.** (토큰만큼)

## 1. 백엔드 — Render (무료 Web Service)

1. Render Dashboard → **New → Blueprint** → 이 저장소 선택 → 루트의 [`render.yaml`](render.yaml) 감지.
2. 환경변수 `OPENAI_API_KEY` 를 Render 대시보드에서 입력 (절대 커밋 금지).
3. 배포 후 URL 확인 (예: `https://rtsgame-backend.onrender.com`).

- 무료 티어는 15분 무활동 시 **슬립** → 첫 요청에 1분+ 콜드스타트. 발표 직전 `/health` 한 번
  호출해 깨워두거나 외부 cron으로 5~10분마다 ping.
- LLM 응답이 수십 초~2분 걸리므로 **서버리스(Vercel/Netlify Functions)에는 백엔드를 두면 안 됩니다**
  (짧은 타임아웃에 끊김). Render 같은 상시 컨테이너여야 합니다.

## 2. 프론트엔드 — Vercel (무료)

1. Vercel → **New Project** → 이 저장소 선택.
2. **Root Directory = `frontend`** 로 지정 ([`frontend/vercel.json`](frontend/vercel.json)이 빌드/SPA 라우팅 처리).
3. 환경변수 **`VITE_API_BASE`** = 위 Render 백엔드 URL (예: `https://rtsgame-backend.onrender.com`).
4. 배포.

`VITE_API_BASE`가 없으면(로컬 dev) 자동으로 Vite 프록시(`/api` → `localhost:8000`)를 씁니다.
프로덕션에서만 이 변수로 실제 백엔드를 가리킵니다. — [frontend/src/api.js](frontend/src/api.js)

## 3. 확인

- 백엔드: `https://<render-url>/health` → `{"status":"ok"}`
- 프론트: Vercel URL 접속 → 프롬프트 생성 → 결과/플레이백 표시.
  (첫 생성은 Render 콜드스타트로 느릴 수 있음.)
