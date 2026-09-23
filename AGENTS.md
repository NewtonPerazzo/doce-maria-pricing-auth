# Doce Maria Pricing — Development Contract

Updated on 2026-09-23. Read this contract before working in any of the three projects.
Keep its copies synchronized when the owner approves a new decision. The current decisions
below supersede earlier exploratory proposals in the conversation.

## Authorized scope

- Frontend: `C:/Users/Neto Perazzo/Documents/doce-maria-pricing`.
- Pricing API: `C:/Users/Neto Perazzo/Documents/doce-maria-pricing-api`.
- Dedicated authentication: `C:/Users/Neto Perazzo/Documents/doce-maria-pricing-auth`.
- Only these three projects may be modified. The authentication project was explicitly
  added to scope by the owner after the initial two-project agreement.
- `C:/Users/Neto Perazzo/OneDrive/Área de Trabalho/fastapi-authentication` may be read as
  a reference only. Never modify it, Manager, or any other project.
- The owner authorized implementation of the projects, backend first, then mobile.
  Initial documentation and store-publication research were completed before implementation.
- Do not invent business rules or add unrequested product features. Explain missing
  requirements and propose options for the owner's decision. Document technical defaults
  and safeguards; do not silently present them as commercial policies.
- Prioritize maintainability, performance, clear English code, Clean Architecture, and SOLID.

## Product and technology

- Run both APIs in Docker Compose by default, together with their MongoDB services;
  Auth also runs Mailpit locally. Document the complete `docker compose up -d --build` command.
- Visible brand: `Doce Maria Precificação`. Do not add slogans or promotional phrases.
- Give each screen a descriptive localized title and provide a standard unmatched-route 404.
- Navigation URLs carry resource IDs only, never serialized ingredient/recipe objects.
  Editors fetch the current entity from the API and preserve the destination through login.
- Costing form fields have concise Portuguese/English help via small library icons, accessible by
  touch, mouse, and keyboard. Tooltips overlay all headings and close on outside press.
  Authentication fields, search, navigation tabs, and new-item actions have no tooltips.
- Separate form sections clearly; use distinct primary actions and segmented navigation/kind/profit
  choices. Other selectors open bottom sheets with chevron buttons. Passwords have visibility toggles.
- Display a branded loading screen during startup, sign-in, and initial catalog loading.
- Recipe and preparation details display component names and consumed quantities with units.
- Selecting a component prefills its purchased/yield quantity and locks its unit; only quantity is
  editable. Existing saved component quantities/units remain intact until another source is chosen.
- Standardize API errors with stable codes, HTTP status, and field validation details;
  translate client-visible errors into Portuguese/English. Distinguish network/timeout/configuration
  failures from authentication and validation failures. Never expose secrets or internal traces.
- Configure app metadata and browser title/language/description. Authenticated application
  pages and the development browser preview must be noindex; native apps do not have web SEO.

- Doce Maria Pricing is a commercial costing tool for confectioners and sellers of cakes,
  pastries, coxinhas, and similar food products.
- FastAPI for the pricing API and the dedicated identity service. MongoDB is approved.
- React Native + TypeScript + Expo for mobile, Redux Toolkit for state/API cache, and
  Atomic Design for presentation components. Pink and gray theme; styled-components allowed.
- All frontend forms must use React Hook Form; useFieldArray manages dynamic recipe rows.
- Default visible language is Portuguese, with i18n support. i18next is used, with Portuguese
  and English catalogs. All identifiers and application code are in English.
- Use npm and package-lock.json only for frontend installation. Do not mix pnpm and npm.
- Prettier formats all frontend sources; Ruff formats/lints Python. Keep readable multiline code.
- The owner validates the visual layout; do not run additional UI/layout browser tests unless requested.
  Continue relevant static checks and calculation/API tests.
- Support iOS and Android. Report real-device verification separately from TypeScript,
  export, browser-preview, and automated test results. Never claim device compatibility untested.
- Expo Go is the initial testing path; use the free EAS tier within its limits for initial
  builds. No paid accounts, paid infrastructure, store publishing, or billing implementation
  has been authorized. Initial mobile delivery precedes future web/Manager integration.

## Authentication boundaries — latest approved design

- `doce-maria-pricing-auth` is a separate identity service for Pricing. It owns signup,
  password hashes, login, expiring access tokens, refresh rotation, logout, and email recovery.
- The frontend talks to Auth for authentication and session verification. It sends access
  tokens when calling the pricing API and stores credentials in native SecureStore, not Redux.
- The pricing API MUST NOT call, import, query the database of, or otherwise communicate
  with an authentication service. No Auth API URL belongs in its configuration.
- The owner explicitly approved **local public-key signature validation** in Pricing.
  The API verifies expiry, token type, issuer, and audience offline. Trusted issuer/public-key
  configuration allows a future Manager identity provider without coupling pricing code to it.
- On 2026-09-23 the owner approved removing the legacy HS256 trust bridge. All providers
  must use RS256 with required sub, iss, aud, exp, iat and type=access. No shared-secret,
  inferred issuer or audience-bypass fallback is permitted.
- Preserve the exact issuer/subject identifiers during provider migration to retain data
  ownership. Migrate external issuers before publishing the strict API; their repositories
  remain outside the authorized modification scope. Apps sharing issuer+subject share data.
- Use signed RS256 access tokens; private keys stay in Auth. Only public keys are distributed
  to resource APIs. Never commit keys, tokens, passwords, or local .env files.
- Scope data ownership by both issuer and subject so identities from different providers
  cannot collide. Actual shared-account mapping with Manager is future work, not assumed.
- The API cannot observe immediate session revocation without contacting another service.
  Frontend session verification detects revocation; already-issued signed tokens remain valid
  at Pricing until their short expiry. The initial configurable access lifetime is 5 minutes.
- Auth defaults: refresh lifetime 7 days, recovery-code lifetime 20 minutes, minimum password
  length 8, maximum 128, request throttling, single-use reset codes, and Argon2id hashing.
  These implementation settings must be documented and may be revised by the owner.
- Local emails go to Mailpit. Production SMTP credentials/provider have not been selected.
- The previous shared-auth/remote-validation proposal is superseded. There is no runtime
  dependency on the old reference service or on any other product.

## Approved costing behavior

- Persist purchased inputs, reusable preparations, and finished products, each with name
  and description. Preparations can contain ingredients and other saved recipes.
- Purchased input fields: name, purchase price, purchase quantity, purchase unit.
  Each recipe component records its referenced input/preparation and quantity consumed.
- Recipes declare their yield quantity and unit. A prepared component contributes its
  proportional **production cost**, never its sale price, to its parent recipe.
- Example: filling costs BRL 30 for 1 kg; using 200 g contributes BRL 6 to a cake.
- Additional costs (labor, gas, electricity, etc.) are named monetary amounts per stored
  recipe yield/batch. Automatic hourly/energy consumption calculators are deferred.
- Support a single yield unit or a requested batch quantity, such as 100 coxinhas.
- Desired profit supports an amount, percentage on cost, or margin on selling price.
  Monetary targets explicitly apply to one yield unit or the entire requested batch.
- Show production cost, calculated sale price, profit amount, percentage on cost, and margin.
  Cost 10 and sale 15 means profit 5, profit on cost 50%, and sale margin about 33.33%.
- Names must be clear: `purchase_price`, `purchase_quantity`, `quantity_used`,
  `production_cost`, `suggested_selling_price`, `calculated_selling_price`, `profit_amount`,
  `profit_on_cost_percentage`, and `profit_margin_percentage`.
- Suggested selling price is production cost multiplied by 1.35: a 35% markup on cost,
  explicitly approved by the owner on 2026-09-18. This includes consumed components and
  additional production costs; it is separate from the user's desired-profit calculation.
  Example: cost BRL 10 -> suggested sale BRL 13.50. This is the product's approved rule,
  not a claim of a universal commercially acceptable profit.
- Keep one current calculation per recipe. Recalculation reads current sources and replaces that
  calculation, preserving its ID/creation date and updating updated_at and source revisions.
  Legacy history is not deleted: promote its newest calculation as current and exclude older
  legacy records from the current-calculation listing. Concurrent updates are atomic.
- Technical conventions: initial currency BRL, exact decimal input/Decimal128 persistence,
  decimal strings over HTTP, 34 significant intermediate digits, 2 displayed monetary
  decimals with ROUND_HALF_UP. Input limits and rounding are documented in the API README.
- Supported initial units: unit, g, kg, ml, l. Convert within dimensions only; never invent
  density conversions. Display per-yield-unit meaning clearly for weight/volume recipes.
- Validate quantities, ownership, revisions, and circular compositions. Technical graph-size
  limits are safeguards, not commercial rules. Do not silently assume taxes, losses, inventory,
  fixed overhead allocation, currency conversion, or a profit recommendation.

## Deferred decisions and release requirements

- Ingredient/recipe deletion policy, offline synchronization, advanced costing, account
  mapping across products, monetization, production infrastructure, and additional currencies.
- Account deletion/data retention and privacy disclosures must be agreed before store release.
- On 2026-09-16, researched store fees were Apple USD 99/year and Google Play USD 25 once;
  new personal Play accounts require at least 12 continuously enrolled closed testers for
  14 days before applying for production access. Recheck rules and prices before publication.
- Sources: https://developer.apple.com/programs/enroll/ and
  https://support.google.com/googleplay/android-developer/answer/6112435 and
  https://support.google.com/googleplay/android-developer/answer/14151465.
- Free EAS usage does not waive Apple account requirements for signed device/store distribution.
  Sources: https://docs.expo.dev/build/setup/ and https://docs.expo.dev/deploy/submit-to-app-stores/.
