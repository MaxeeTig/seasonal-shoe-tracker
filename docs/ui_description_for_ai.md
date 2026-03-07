# UI Requirements for AI Interface Generation

## Product context
A mobile-first web app to track seasonal shoe storage.
Core model: `pair of shoes -> box -> location`.
Primary user goal: quickly answer “Where are my shoes?” and “What is inside this box?”.

## Language and localization
- All UI text must be in Russian.
- All tags and enum values must be in Russian.
- Example mapping for understanding only (do not show EN in UI):
  - `winter sneakers` -> `зимние кроссовки`.

## Platform and visual direction
- Platform: mobile browser first.
- Style: clean, practical, warm neutral palette, strong contrast.
- Avoid tiny controls and dense desktop-like tables.
- Prefer cards, clear sections, and short labels.

## Main screens
1. **Store Shoes (`Сложить обувь`)**
- Fields:
  - Название пары (text)
  - Фото обуви (file/camera)
  - Сезон (select: `зима`, `весна`, `лето`, `осень`)
  - Тип обуви (text)
  - Цвет (text)
  - Пол/стиль (select: `мужской`, `женский`, `унисекс`)
  - Фото коробки (file/camera)
  - Цвет коробки (text)
  - Форма коробки (text)
  - Особые признаки (text, comma-separated)
  - Визуальный отпечаток (text)
  - Фото места (optional file/camera)
  - Зона (text)
  - Место (text)
- AI buttons:
  - `AI: распознать обувь`
  - `AI: распознать коробку`
  - `AI: распознать место`
- Primary action: `Сохранить`.

2. **Find Shoes (`Найти обувь`)**
- Search input (text): e.g., `зимние кроссовки`.
- Season filter (select, optional).
- Action button: `Поиск`.
- Result card content:
  - Shoe photo
  - Box photo
  - Name/title
  - Season, type, status
  - Location path: `Зона -> Место`
  - Box id
  - Quick actions: `Взял обувь`, `Вернул на хранение`

## Interaction requirements
- For each selected image, show immediate preview under file input.
- AI action buttons must be visually prominent and clearly tappable.
- While AI request is running:
  - Disable clicked AI button.
  - Replace button label with `Распознавание...`.
  - Show status text describing current operation (e.g., `Распознавание обуви...`).
- After AI completion:
  - Show success/clarification status text.
  - Keep editable fields so user can adjust recognized values.
- On save:
  - Show `Сохранение...` then success/error message.

## Domain behavior reflected in UI
- One box contains one pair of shoes.
- No UI for matching/reusing previously saved boxes.
- Each save flow creates a new box record for the current pair.
- Show helper note in store flow: each pair is stored in a separate box.

## Status and feedback
- Provide a dedicated status area in store form.
- Status types:
  - progress (`Распознавание...`, `Сохранение...`)
  - success (`Сохранено: пара #...`)
  - error (`Ошибка: ...`)
- Error messages should be short, readable, and near active form.

## Accessibility and usability
- Touch targets >=44px height.
- Minimum text size 14px.
- Inputs and buttons must be high-contrast.
- Preserve visible focus state for keyboard users.
- Do not rely on color only; use text status too.

## Responsive behavior
- Breakpoint at 900px.
- Mobile (<900):
  - Single-column layout.
  - Sticky bottom action bar for main action (`Сохранить`) if possible.
  - Keep status area visible above keyboard-sensitive zones.
- Desktop (>=900):
  - Centered content container.
  - Comfortable max width (around 860–960px).
  - Maintain same flow and labels as mobile.

## Components and layout guidance
- Use section cards:
  - Header/connection badge
  - Store Shoes card
  - Find Shoes card
- Use consistent vertical spacing (8/12/16 rhythm).
- Keep forms short visually with grouped rows where appropriate.
- For mobile, avoid horizontal scrolling.

## Data labels and controlled vocab (RU)
- Seasons: `зима`, `весна`, `лето`, `осень`.
- Gender/style: `мужской`, `женский`, `унисекс`.
- Typical shoe types (examples): `кроссовки`, `ботинки`, `сланцы`, `туфли`.
- Status labels: `хранится`, `в использовании`.

## Output expectation for AI UI generator
Produce:
1. Screen structure and component tree.
2. Microcopy in Russian for all controls and states.
3. Responsive rules for <900 and >=900.
4. Interaction states (idle/loading/success/error).
5. Accessibility notes implemented in component props/styles.
