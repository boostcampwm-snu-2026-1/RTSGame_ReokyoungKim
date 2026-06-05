# 개발 Task 목록

### [infra] 실제 LLM end-to-end 생성 테스트 1회 실행 및 결과 검증
- **설명**: 현재 README 검증 상태에 "실제 LLM 생성은 아직 미실행"으로 명시되어 있다. `backend/.env`에 `OPENAI_API_KEY`를 넣고 `python pipeline.py "<query>"`를 최소 1회 돌려 3-step 파이프라인(find_scenario → load_existing_mode → ScriptDeveloperAgent.run)이 끝까지 동작하고 유효한 config JSON을 산출하는지 확인한다. 핵심 흐름이 실가동된 적 없으므로 가장 우선순위 높은 검증 작업이다.
- **완료 기준(DoD)**:
  - [ ] 5개 시나리오(Fixed-Field Skirmish FFA/Team, Multi-Front Defense, Siege Planning, Time-Phased Production) 각각에 대해 매칭되는 query로 1회씩 생성 성공
  - [ ] 생성된 config가 information / end_condition / unit_placement / customize 4개 블록을 모두 포함
  - [ ] `backend/log/<timestamp>/result/scenario_normal.json` 산출물 확인 및 README 검증 상태 업데이트
- **제안 브랜치**: feature/e2e-generation-test

### [backend] DBCall 쿼리 기반 시나리오 자동선택 정확도 개선 및 fallback 처리
- **설명**: `find_scenario`는 `DBCall.call_with_names`의 LLM 매칭 결과 중 `names[0]`만 사용하고, 매칭 실패 시 `no_matching_scenario` 에러로 끝난다. 유사 시나리오가 하나도 안 잡히는 query에 대한 fallback(기본 시나리오 또는 상위 N개 후보 제시)이 없어 사용성이 떨어진다. 매칭 신뢰도와 fallback을 보강한다.
- **완료 기준(DoD)**:
  - [ ] 매칭 실패 시 가장 일반적인 기본 시나리오로 fallback하거나 후보 목록을 응답에 포함
  - [ ] `_resolve_db_name` fuzzy 매칭이 LLM 반환명과 DB 실제 키 불일치 케이스를 커버하는지 단위 테스트 추가
  - [ ] 매칭된 시나리오명과 매칭 근거(reason)를 `/generate` 응답에 포함해 프론트에서 표시 가능
- **제안 브랜치**: feature/scenario-auto-select

### [backend] 난이도 분기(easy/normal/hard) 복원
- **설명**: v4 대비 단순화로 난이도가 `normal` 단일로 고정되었다(`script_builder.py`의 `difficulties = ["normal"]`, `place_units`/`generate_rule_config`/`get_condition` 모두 "normal" 하드코딩). 유닛 수·웨이브 간격·승패 조건을 난이도별로 분기해 generation 다양성을 복원한다.
- **완료 기준(DoD)**:
  - [ ] `difficulties`를 파라미터화하여 easy/normal/hard 중 선택 가능
  - [ ] 난이도별로 unit_placement 수량 또는 customize(웨이브 spawner) 파라미터가 실제로 차등 적용
  - [ ] `/generate` 요청에 난이도 옵션 추가, 응답 `final_json`에 난이도별 config 포함
- **제안 브랜치**: feature/difficulty-branching

### [backend] 시나리오 DB 추가 및 메타데이터 정비
- **설명**: 현재 `db/scenario`에는 5개 시나리오만 존재한다. 매칭 폭을 넓히기 위해 신규 시나리오(예: 자원 러시, 호위/escort, 점령전)를 추가하고, 각 시나리오의 `specification`·참조 rule·decision·meta.json description을 정비한다. LLM 매칭 품질은 description 품질에 직결되므로 함께 손본다.
- **완료 기준(DoD)**:
  - [ ] 신규 시나리오 2개 이상 추가(specification + 참조 rule + meta.json description)
  - [ ] 추가 시나리오가 참조하는 rule이 `db/rule/codes`에 검증본(.lua)으로 존재하는지 확인
  - [ ] `/catalog` 응답에 신규 시나리오가 정상 노출되고 query 매칭 동작 확인
- **제안 브랜치**: feature/add-scenarios

### [backend] 자동화 테스트 추가 (pytest)
- **설명**: 백엔드에 테스트가 전무하다(`find -iname '*test*'` 결과 없음). LLM 호출을 모킹해 파이프라인 구조·DB 로딩·config 조립 로직을 회귀 테스트로 보호한다.
- **완료 기준(DoD)**:
  - [ ] `load_existing_mode`, `_resolve_db_name`, `assemble_draft` 등 순수 로직 단위 테스트 작성
  - [ ] LLM 클라이언트를 모킹한 `pipeline.generate` 통합 테스트(스모크) 추가
  - [ ] `pytest`가 로컬에서 통과하고 requirements에 테스트 의존성 명시
- **제안 브랜치**: feature/backend-tests

### [infra] GitHub Actions CI 구성
- **설명**: `.github`가 없어 CI가 전혀 없다. PR(feature → dev) 시 백엔드 테스트와 프론트엔드 빌드를 자동 검증하는 워크플로를 추가한다.
- **완료 기준(DoD)**:
  - [ ] `.github/workflows/ci.yml`에서 Python pytest 실행 job 구성
  - [ ] 동일 워크플로에서 `npm ci && npm run build` 프론트 빌드 검증 job 구성
  - [ ] dev 및 feature/* 브랜치 대상 PR에서 CI 트리거 확인
- **제안 브랜치**: feature/ci-setup

### [frontend] 생성 에러 처리 및 로딩 UX 개선
- **설명**: `App.jsx`는 에러를 단일 문자열 배너로만 표시하고, 로딩은 정적 텍스트뿐이다. `no_matching_scenario`/`failed_to_load_scenario` 같은 백엔드 에러 코드별 안내, 재시도 버튼, 단계별 진행 표시(매칭→스크립트)를 추가해 LLM 호출(수십 초) 동안의 UX를 개선한다.
- **완료 기준(DoD)**:
  - [ ] 백엔드 에러 코드별로 사용자 친화적 한국어 메시지 매핑 및 재시도 버튼 제공
  - [ ] 로딩 중 단계별(스피너/진행 인디케이터) 표시
  - [ ] 빈 config·부분 결과 응답에 대한 방어 처리(크래시 없음)
- **제안 브랜치**: feature/error-loading-ux

### [frontend] MiniMap·SimPlayback 맵 매칭 로직 안정화
- **설명**: `App.jsx`의 `mapMeta` 추론은 `map_name`을 catalog 맵 이름 첫 단어로 `includes` 비교하는 취약한 휴리스틱이라 잘못된 맵 크기를 잡을 수 있다. `SimPlayback`/`MiniMap`은 mapMeta가 없으면 유닛 좌표로 월드 크기를 추정해 스케일이 틀어진다. 맵 매칭을 견고하게 만든다.
- **완료 기준(DoD)**:
  - [ ] map_name → catalog 맵 정규화 매칭(공백/버전 접미사 제거 후 비교)으로 교체
  - [ ] mapMeta 미발견 시 캔버스에 경고/추정 모드 표시
  - [ ] 대표 시나리오 2종에서 유닛 좌표가 맵 경계 안에 올바른 스케일로 렌더링되는지 확인
- **제안 브랜치**: feature/map-matching-fix

### [frontend] SimPlayback 유닛 분류·교전 근사 로직 정확도 개선
- **설명**: `SimPlayback.jsx`의 `isStructure`는 unit code suffix 문자열 매칭(lab/solar/mex 등)에 의존하는 거친 분류라 신규 유닛에서 오분류가 잦다. `info/units_info.json`의 실제 유닛 메타(구조물/이동 여부, 무기 사거리)를 활용해 이동/교전/웨이브 스폰 근사를 개선한다.
- **완료 기준(DoD)**:
  - [ ] units_info 기반 유닛 분류로 교체(하드코딩 hint 제거 또는 보조용으로 축소)
  - [ ] 교전 사거리·이동 속도에 유닛 메타 반영
  - [ ] 대표 시나리오에서 재생/정지/리셋/속도 컨트롤과 승패 판정이 정상 동작
- **제안 브랜치**: feature/simplayback-accuracy

### [infra] 배포 설정 및 프로덕션 실행 가이드
- **설명**: README의 실행 방법은 "예정"으로 표기된 로컬 dev 절차뿐이고, 배포 구성이 없다. 백엔드 컨테이너화와 프론트 정적 빌드 서빙(프록시 포함) 구성을 추가해 단일 명령으로 띄울 수 있게 한다.
- **완료 기준(DoD)**:
  - [ ] 백엔드 Dockerfile(uvicorn) 및 프론트 빌드 산출물 서빙 구성 추가
  - [ ] docker-compose 또는 동등 스크립트로 backend(8000)+frontend 동시 기동
  - [ ] 프로덕션 환경에서 `/api` 프록시 또는 CORS 경로가 동작하는지 확인
- **제안 브랜치**: feature/deploy-setup

### [backend] 코드 정리 — 미사용 verify/refine 잔재 및 더미 파일 제거
- **설명**: 단순화로 analyst/verify 루프가 제거됐지만 `script_builder.py`에는 `verify_script`/`refine_script`/`check_script_validity`/`_log_feedback`와 `is_script_valid`·`loop_count` 상태가 그대로 남아 있고(그래프에서 미사용), `__main__` 블록은 존재하지 않는 designer 로그 경로를 참조한다. `info/map copy.json` 같은 더미 파일도 있다. 데드코드를 정리한다.
- **완료 기준(DoD)**:
  - [ ] 미사용 메서드/상태(verify/refine/check/feedback 로그) 및 관련 state 필드 제거 또는 명확히 분리
  - [ ] `__main__` 테스트 진입점을 현 파이프라인에 맞게 수정 또는 제거
  - [ ] `info/map copy.json` 등 불필요 파일 정리 후 import·그래프 빌드 정상 확인
- **제안 브랜치**: feature/cleanup-deadcode

### [docs] README 및 Wiki 문서 최신화
- **설명**: README 아키텍처 다이어그램이 실제 모듈명과 어긋난다(`generator.py` 언급 → 실제는 `pipeline.py`/`script_builder.py`, SimPlayback 컴포넌트 미기재). 또한 `seed` 파라미터, `/catalog` 응답 스키마, 좌표계(타일=512px) 설명을 정비하고 기여/브랜치 전략을 Wiki로 옮긴다.
- **완료 기준(DoD)**:
  - [ ] README 모듈명·컴포넌트 목록(SimPlayback 포함)·API 스키마를 실제 코드와 일치시킴
  - [ ] `seed` 옵션과 catalog/generate 응답 예시 문서화
  - [ ] 브랜치 전략(main→dev→feature/*)·기여 가이드를 Wiki 또는 CONTRIBUTING으로 정리
- **제안 브랜치**: feature/docs-update
