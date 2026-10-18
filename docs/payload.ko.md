# imagespec payload 작성

[English](payload.md) | **한국어**

통합과 다른 호스트가 사용하는 공통 이미지 명세를 설명합니다. 렌더러는 이미지를 만들며 기기 발견·Bluetooth 전송·라벨 인쇄·화면 갱신을 수행하지 않습니다. 실제 액션 이름·대상·상위 입력 필드·기기 설정은 해당 통합의 payload 안내를 따르세요. 아래 라이브러리 예제는 HA·하드웨어 없이 로컬에서 실행합니다.

## Payload와 호스트 액션의 차이

imagespec payload는 순서대로 그리는 **요소 매핑의 목록**입니다. 각 항목에는 `type`과 해당 요소의 속성이 있습니다. 좌표는 왼쪽 위 기준 픽셀이며 나중 요소가 앞의 요소를 덮을 수 있습니다. `group`·`stack`·`row`·`column`은 자체 배치 규칙에 따라 자식 `elements`를 포함할 수 있습니다.

```yaml
- type: text
  x: 12
  y: 12
  value: "Hello, imagespec"
  size: 22
  color: black
```

이는 payload 자체이며 완전한 HA 액션이 아닙니다. 호스트는 목록을 `payload` 필드 아래에 두고 기기별 대상·출력 설정을 함께 받거나 다른 입력 방식을 사용할 수 있습니다. 임의의 공통 액션 틀을 자동화에 붙여 넣지 마세요. Python API는 파싱된 목록을 받습니다. 너비·높이·전체 회전·디더링은 별도 `render()` 인자이며 팔레트·resolver는 `RenderContext`에 둡니다. 이 설정이 자동으로 payload 요소가 되거나 모든 HA 액션의 입력으로 제공되지는 않습니다.

실제 키·필수값·기본값·중첩 옵션은 [요소 예제](elements.md)(영어)와 생성된 [속성 참조](reference.md)(영어)를 확인하세요. [작성 안내](authoring.md)(영어)는 배치 선택과 완성 장면을 설명합니다. [JSON Schema](../schema/elements.json)는 편집기 검사에 활용할 수 있으며 통합이 사용하는 imagespec 버전과 비교해야 합니다.

## 최소 동작 예제

[examples/payload/minimal.yaml](../examples/payload/minimal.yaml)은 **296 × 128**, 흑백 팔레트·회전 없음의 시연용 캔버스에서 동작하는 오프라인 payload입니다. 크기는 예시이며 실제 기기 지원을 주장하지 않습니다. 사각형 테두리·기본 내장 글꼴의 텍스트·수평선을 포함합니다. 실제 기기에 맞춰 크기와 좌표를 함께 조정하세요.

이 checkout에서 Python **3.13+**와 선택 YAML extra를 사용해 읽고 렌더링할 수 있습니다.

```bash
python -m pip install '.[yaml]'
python - <<'PY'
from pathlib import Path

import yaml
from imagespec import RenderContext, RenderError, render, validate

payload = yaml.safe_load(Path("examples/payload/minimal.yaml").read_text())
issues = validate(payload)
if issues:
    raise SystemExit("\n".join(map(str, issues)))

try:
    image = render(
        payload,
        width=296,
        height=128,
        rotate=0,
        rotate_mode="canvas",
        background="white",
        dither=False,
        strict=True,
        context=RenderContext(palette="bw"),
    )
except (RenderError, ValueError) as exc:
    raise SystemExit(str(exc)) from exc

image.save("/tmp/imagespec-minimal.png")
print(image.mode, image.size)
PY
```

예상 출력은 `RGB (296, 128)`이며 픽셀은 검정·흰색뿐입니다. 파일은 미리보기이며 기기로 전송되지 않습니다. `yaml` extra는 PyYAML을 제공하며 호스트가 이미 Python 딕셔너리를 제공하면 YAML 파싱은 필요하지 않습니다. 외부 이미지·다운로드 글꼴·history provider·추가 바코드 의존성 없이 렌더링합니다.

## 값·템플릿·표시 여부

일반 YAML 숫자·불리언을 우선 사용하세요. 선언된 숫자 필드는 `x: "12"`·`size: "22"` 같은 문자열도 받고 불리언은 `"False"`·`"off"`·`"0"`도 받습니다. `visible: false`는 요소를 숨깁니다. 선택 키 생략 시 기본값을 사용하며 `null`도 대체로 생략과 같습니다. 다만 색상의 `null`은 채움·윤곽 없음, 요소 `dither`의 `null`은 전체 설정 상속이며 특별한 의미가 명시된 필드도 있습니다. 모든 `null`이 같은 동작이라고 가정하지 말고 해당 속성의 참조를 읽으세요.

HA/Jinja 템플릿은 imagespec에 값을 전달하기 전 **호스트 통합**이 처리합니다. imagespec은 선언된 숫자·불리언 문자열을 변환할 뿐 `{{ ... }}`를 평가하거나 HA 상태를 읽거나 공통 템플릿 문법을 제공하지 않습니다. Jinja 표현식이 그대로 남은 좌표는 숫자가 아닙니다. 통합의 템플릿 지원 필드를 확인하고 최종 값을 확인하세요. 일반 텍스트의 중괄호는 호스트가 처리하지 않으면 그대로 텍스트입니다.

YAML 들여쓰기·따옴표도 중요합니다. HEX 색상은 `"#ff0000"`처럼 감싸 `#`가 주석이 되지 않도록 하고 매핑 키는 한 줄에 하나씩 적습니다. 호스트가 목록과 YAML 문자열 중 무엇을 받는지 확인하세요. 상위 입력의 파싱은 호스트 책임입니다.

## 크기·색상·회전·디더링

실제 모델 크기·지원 색상·기기 인코딩은 통합이 정합니다. 요청한 색상을 그려도 하드웨어 색상이 추가되지는 않습니다.

| 설정 | 공통 동작 | 기기별 결정 |
|---|---|---|
| 너비 / 높이 | 양수인 렌더링 픽셀 크기 | 패널 해상도·인쇄 폭/라벨 크기·용지 제한·액션 필드 |
| 팔레트 | `RenderContext(palette="bw")`, `"bwr"`, 다른 명명 팔레트 또는 지원 색상 목록 | 실제 모델 색상. 모든 전자종이가 빨강을 지원하거나 프린터 폭이 같다고 가정하지 않음 |
| 요청 색상 | 이름·따옴표로 감싼 HEX. 최종 RGB 픽셀은 팔레트로 매핑 | 팔레트 밖 색상은 달라지므로 모델 팔레트로 미리보기 비교 |
| `rotate` | 전체 `0`·`90`·`180`·`270`도 시계방향 회전 | 물리적 방향과 통합의 회전 설정 제공 여부 |
| `rotate_mode="canvas"` | 90/270도에서 그리는 면은 높이 × 너비, 출력은 너비 × 높이 유지 | 고정 해상도 화면 |
| `rotate_mode="image"` | 너비 × 높이로 그린 뒤 회전, 출력은 높이 × 너비 | 가변 라벨처럼 출력 크기 교환을 허용하는 호스트 |
| `dither` | `False` / `"none"`: 가장 가까운 팔레트 색상. `True` / `"floyd"`: Floyd–Steinberg. `"atkinson"`·`"bayer8"` 등도 지원 | 통합의 전체/요소별 설정 제공 여부와 실제 가독성 |

296 × 128 호출에서 `rotate=90`이면 canvas 모드는 128 × 296에 그려 296 × 128을 반환하고 image 모드는 296 × 128에 그려 128 × 296을 반환합니다. 0/180도에서는 두 모드의 크기가 같습니다. 요소 회전은 전체 캔버스 회전과 별개입니다. imagespec 1.1.0부터 자체 `rotate` 필드가 없는 요소는 시계방향 `rotate: 0`·`90`·`180`·`270`을 받습니다. 기존 요소별 회전은 문서화된 의미를 유지합니다. `text.rotation`은 반시계방향이며 `dlimg.rotate`는 시계방향으로 EXIF 방향 적용 후 크기 변경 전에 수행합니다. 사용 전 설치된 버전과 요소 참조를 확인하세요.

지원 알고리즘 이름은 설치된 라이브러리의 `DITHER_METHODS` 또는 [디더링 참조](dithering.md)(영어)를 확인하세요. 디더링은 팔레트 색상으로 중간 톤을 표현하며 실제 물리 색상을 추가하지 않습니다. 요소별 `dither`로 전체 설정을 덮어쓸 수 있습니다. 선명한 텍스트·QR·바코드부터 시작하고 사진·차트에서 가독성이 좋아질 때 디더링을 사용하세요. QR·바코드 모듈 크기는 실제 출력 해상도에 맞게 확보하고 실물에서 읽히는지는 별도 확인합니다.

## 글꼴·이미지·이력·선택 기능

- **글꼴:** 기본 `NotoSansKR-Regular.ttf`가 포함됩니다. 호스트 `font_resolver` → 이름이 같은 내장 글꼴 → 기본 내장 글꼴 순서로 찾으므로 요청 글꼴이 없어도 오류 대신 대체될 수 있습니다. 다른 문자권·장식 글꼴은 적절한 라이선스 파일과 호스트 resolver가 필요할 수 있습니다. 라이브러리는 HA `www/fonts` 경로를 가정하지 않으며 통합이 경로 조회를 제공합니다. 다운로드·캐시 resolver도 호스트가 설정할 때 사용하는 기능이지 모든 통합의 자동 다운로드를 뜻하지 않습니다. [글꼴과 자산](../README.md#fonts--assets)(영어)을 참고하세요.
- **아이콘·코드:** 내장 MDI·Font Awesome Free 자산에서 문서화된 이름을 사용합니다. 유료 Font Awesome 아이콘이 포함된다고 가정하지 마세요. `datamatrix`는 선택 `datamatrix` extra(`pyStrich`)가 필요합니다. QR·바코드는 요소 참조를 따릅니다. `fast` extra는 numpy 디더링 가속이며 기기 기능을 추가하지 않습니다.
- **이미지(`dlimg`):** HTTP(S)·`data:` URL을 지원합니다. 로컬 경로는 호스트의 `allow_local_images=True`가 없으면 비활성입니다. 호스트 파일 경로나 브라우저에서 열리는 URL이 통합 실행 환경에서도 접근된다고 가정하지 마세요. 인증·세션 처리는 호스트 `image_fetcher`가 필요하며 공개 예제에 비밀값을 넣지 않습니다. 기본 HTTP 다운로드는 크기 제한(`max_image_bytes`, 기본 20 MiB)과 선택 TTL 캐시(기본 꺼짐)를 사용합니다. 사용자 fetcher는 bytes를 반환하므로 필요한 스트리밍 메모리 제한은 직접 적용해야 합니다. Python context 옵션이며 HA 액션 필드 제공을 보장하지 않습니다.
- **이력(`plot`):** 호스트 `history_provider`가 필요합니다. imagespec이 HA recorder를 import하거나 엔티티·이력을 자동 조회하지 않습니다. 직접 데이터를 받는 차트는 각자의 스키마를 따릅니다. 다른 통합 예제에 이력이 있다고 현재 통합에서도 `plot`을 추가하지 마세요.

## 검증과 문제 해결

`validate(payload)`는 `Issue(path, message)` 목록을 반환하며 빈 목록은 선언된 스키마 문제를 찾지 못했다는 뜻입니다. 미지원 type·키·필수값·선언된 타입·관련 enum·색상 등을 확인합니다. 글꼴 존재·이미지 URL 응답·이력 제공·기기 안에 들어가는 배치·실제 기기 동작까지 검증하지는 않습니다. 검사 후 실제 호스트 기능으로 렌더링하세요.

`render(..., strict=True)`는 같은 검사를 먼저 수행하고 문제를 모아 `RenderError`로 알립니다. strict가 없으면 모르는 키는 대체로 무시하고 미지원 요소 type은 로그를 남기고 건너뛰므로 예외 없이 미리보기가 누락될 수 있습니다. 관대한 렌더링에 의존하지 말고 검증으로 오타를 찾으세요. 지원 여부는 최신 온라인 예제가 아니라 설치된 버전의 `known_types()`와 참조를 기준으로 판단합니다.

핸들러 오류는 요소 문맥을 포함한 `RenderError`로 전달됩니다. `err.path`는 요소·중첩 자식 위치(예: `[1].elements[0]`), `err.message`는 경로 없는 메시지이며 `str(err)`에는 경로가 포함됩니다. 잘못된 전체 크기·회전·회전 모드는 `ValueError`일 수 있습니다. 모든 오류가 `RenderError`이거나 기기 장애인 것은 아닙니다.

| 문제 | 먼저 확인 |
|---|---|
| 빈 화면·요소 누락 | `visible`, type 철자·버전, 좌표·잘림·나중 요소 덮임, `validate()` 실행 |
| 모르는 키·필수 키 누락 | 해당 요소의 정확한 속성과 오류 경로. 무관한 요소를 바꾸지 않음 |
| 숫자값 오류 | 호스트 템플릿 최종 결과·상태 없음/사용 불가·숫자 기본값. imagespec은 Jinja를 평가하지 않음 |
| 크기·방향·잘림 오류 | 실제 모델 크기·전체 회전 모드·요소 좌표를 같은 출력 설정으로 미리보기 |
| 색상 변경·가독성 저하 | 실제 팔레트·디더링·글자/모듈 크기. 미리보기는 실물 가독성 검증이 아님 |
| 글꼴·이미지 없음 | 호스트 resolver·경로·URL 접근/인증·글리프·필수 자산 |
| 이력 없음 | 실제 `history_provider` 제공 여부. 적합할 때만 직접 데이터 요소 사용 |
| 미리보기 성공·기기 갱신 실패 | 통합의 전송·기기 문제 해결로 돌아가기. 이미지 생성과 전달은 별개 |

도움은 해당 통합의 기존 Issues·지원 경로와 기기별 payload 안내를 이용하세요. 설치된 통합/imagespec 버전·실제 크기/팔레트/회전·최소 비식별 payload·정확한 오류와 로컬 렌더링/기기 전송 중 어느 쪽이 실패했는지 기록합니다. 비공개 엔티티명·이미지·URL·주소·인증 정보는 제거하세요. 별도 공통 제보를 중복 생성하지 말고 기존 절차를 따릅니다. 개발용 기능은 [호스트 통합 안내](integrating.md)(영어)를 참고하세요.
