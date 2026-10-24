# Visual boards API contract
All routes below use `/api/projects/{project_id}` (project = existing Epic).

- GET/POST `/boards`: list full boards / create with `{name, objects?: [], view?: {x:0,y:0,zoom:1}}`.
- GET `/boards/{board_id}`: full board.
- PUT `/boards/{board_id}`: save complete `{name, revision, objects, view}`. Revision is required, atomically checked; success increments it. Rename uses the same endpoint/payload.
- POST `/boards/{board_id}/copy`: `{name, objects, view}` creates independent board using supplied LOCAL state, retaining source references. For ordinary duplicate send fetched state.
- DELETE `/boards/{board_id}?revision=N`: checked deletion; preserves source assets.
- GET `/assets`: combined project library, including completed/archived items and legacy epic membership, deduplicated.
- POST `/assets`: multipart `file`, optional `caption`; upload only, returns one asset. Each file is an independent request.
- DELETE `/assets/{asset_id}`: project-owned source deletion, blocked when used.

Board: `{id, project_id, name, revision, objects, view, assets, created_at, updated_at}`. `assets` includes referenced source metadata even after source item moves away. Initial revision 1.

Objects (array order is back-to-front layer order): common `{id: string, type: 'image'|'text'|'swatch', x:number, y:number, width:positive number, height:positive number}`. Image additionally `{asset_key:'item:123'|'project:123'}`; text `{text:string}`; swatch `{color:'#RRGGBB'}`. Do not send irrelevant properties or UI selection state. IDs unique within board. All coordinates finite; view zoom > 0. Image aspect ratio is maintained by client.

Asset: `{key, id, kind:'item'|'project', file_url, original_filename, caption, item_id:null|number, source_name:string}`. Original uploads remain unchanged; image placements reference key.

Error shapes: FastAPI `{detail:...}`. 404 missing project/board; 422 invalid payload; 400 invalid upload/reference. 409 save/delete conflict `{detail:{code:'revision_conflict',message:'...',latest:<full board>}}`; local state must remain untouched. Retry with latest revision only after explicit compare/replace confirmation. 409 source deletion `{detail:{code:'asset_in_use',message:'...',boards:[{id,project_id,name}]}}`, including existing DELETE `/api/assets/{id}`.
