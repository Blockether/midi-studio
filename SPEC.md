# SPEC — Vis playground on AWS Lambda

Every fact below comes from the project README and from no other source.

## Purpose

The product runs Vis as a service on AWS Lambda, with Amazon S3 as its database and a GitHub repository copied onto Amazon EFS as the project of each session, and offers a web application of four pages, a Vis extension and a set of workflows on the Vis SDK.

## Actors

| Actor | What it does |
| --- | --- |
| Person with the password | Signs in on a page, uses the four pages, downloads transcripts, artifacts and temporary files, starts and cancels runs, gives a file to a waiting run, publishes work |
| Script or SDK caller | Calls `/v1/*` and `/play/api/*` with `Authorization: Bearer <password>`; `decide.py` is the example |
| Vis session (the model) | Runs inside a worker, writes documents with `attach`, calls the verbs of the `playground` extension |
| GitHub | Calls `POST /hooks/github` with its signature; receives the pushes that `repo` makes |
| Model provider | Serves the OpenAI-compatible API that `llm` calls with the provider key |
| Operator | Runs `deploy.sh`, changes the parameters, removes the stack |

## Components

| Component | Network | Holds | Work |
| --- | --- | --- | --- |
| `front` | public address | the password, the webhook secret | Checks the password, serves the pages and Vis web, sends each call to the worker through SQS, streams the answer from S3, starts a worker when work waits |
| `worker` | VPC, no internet | no secret | Runs the Vis gateway, the sessions and the workflow runs; saves the Vis home directory to S3 |
| `llm` | outside the VPC, internet access, no public address | the provider URL and key | Accepts `GET /models` and `POST /chat/completions`, adds the key, streams the answer |
| `repo` | outside the VPC, internet access, no public address | the GitHub deploy key | Copies the `main` branch to S3; pushes the commits of a session |
| `sync` | VPC, no internet | no secret | Puts a snapshot on EFS and makes it the current release |

Supporting parts: `playground/runtime.py` (the Lambda Runtime API on the standard library, plain and streamed answers), S3 (database), SQS (call queue), EFS (`releases/`, `CURRENT`, `work/`), the pages under `web/`, `extension/playground.py`, the six workflows under `workflows/`, `decide.py`, `template.yaml`, `deploy.sh` and `python -m playground.local`.

## Interfaces

**HTTP.** The address of the stack is the Function URL of `front`, the output `Url` of the stack. A body and an answer of the playground API are JSON. The pages, `/v1/*` and `/play/api/*` need the password, as `Authorization: Bearer <password>` or as the cookie of a sign-in; a browser call that changes data must come from a page of the stack.

| Address | Password | Result |
| --- | --- | --- |
| `POST /login`, `POST /logout` | the form field `password`; none | Sets the cookie for 7 days and opens `/play`; removes the cookie |
| `POST /hooks/github` | none; the signature of GitHub | Starts a fetch of `main` |
| `GET /play/assets/*`, `GET /play/vendor/*`, `GET /<file>` | no | The scripts, styles, editor and fonts of the pages; the static files of Vis web |
| `GET /`, `/play`, `/play/workflows`, `/play/factory`, `/play/architecture` | yes; without it the sign-in page | The pages |
| `/v1/*` | yes | The Vis gateway: sessions, turns, events, attached files |
| `/play/api/*` | yes | The playground API of the worker |

**Playground API**, below `/play/api/`.

| Group | Calls |
| --- | --- |
| Status | `GET status` — release, project directory, repository, models, worker start time, runs queued or running |
| Workflows | `GET workflows`, `POST workflows/check` `{source}`, `GET workflows/<name>`, `PUT workflows/<name>` `{source}`, `DELETE workflows/<name>` |
| Runs | `GET runs`, `POST runs` `{workflow, input}`, `GET runs/<id>`, `POST runs/<id>/cancel`, `GET runs/<id>/inputs/<key>`, `POST runs/<id>/inputs/<key>` `{name, content}` |
| Files | `GET artifacts?session=<id>`, `GET artifacts/<session>/<name>`, `GET tmp?session=<id>`, `GET tmp/<session>/<path>` |
| Publish | `POST publish` `{root, message}` |
| For the run process | `POST runs/<id>/events` `{type, …}`, `GET runs/<id>/results/<n>` |
| For the extension hook | `POST tmp` `{session, files, removed}` |

**Workflow SDK.** `@workflow(title=, description=, model=)` marks the one function a run calls, its arguments after `ctx` being the inputs; `@activity(title=)` makes a function a recorded step with `ctx` as first argument. Inside an activity: `ctx.ask(request, Model)` returns a validated Pydantic object, `ctx.ask(request)` returns the text of the answer, `ctx.document(name, request)` returns an `Artifact` (`name`, `session`, `size`, `version`), `ctx.receive(key, title, accept=".md,.txt")` returns an `Upload` (`key`, `name`, `size`, `text`), `ctx.note(text)` adds a line to the log of the run.

**Extension verbs** for each session, alias `playground`: `workflows()`, `run_workflow(name, input)`, where `input` is an object of the inputs or a text for the first input, `run_status(run_id)`, `publish(message)`. In Vis web, `/workflows` opens a panel that starts a workflow and shows its runs, and `/workflows <name> <input>` starts a run without the panel.

**Vis SDK.** `session.attachments()`, `session.attachments(-1)`, `session.attachments(turn_id)` and `session.attachments([0, -1])` list the metadata of the attached files of the whole conversation, of the last turn, of one turn or of some turns; `file.read()` and `file.text()` download a file. When a session attached a name more than one time, the list has each version, and a file that a person sent with a request is not in the list. These calls need `vis-agent` 0.5.18 or later and a gateway of the same Vis version.

**Model verbs of a session** for documents: `attach(content.encode(), "SPEC.md")`, `list_attachments()`, `read_attachment("SPEC.md")`.

## Data

S3 keys and their retention.

| Key | Content | Kept for |
| --- | --- | --- |
| `lease.json` | the active worker, its last checkpoint, the work that waits | permanent |
| `state/<worker>/<n>.tar.gz` | a checkpoint of the Vis home directory: sessions, transcripts, attached files, settings | the last one; a checkpoint of a failed worker stays |
| `workflows/<name>.py` | the source of a workflow | permanent |
| `runs/index.json` | one line for each of the 300 newest runs | permanent |
| `runs/<run>/run.json` | the record of a run and of its workflow activities | permanent |
| `runs/<run>/workflow.py` | the source the run uses, also after an edit of the workflow | permanent |
| `runs/<run>/results/<n>.json` | the result of workflow activity `n` | permanent |
| `runs/<run>/inputs/<key>.json` | a file a person gave to a waiting run | permanent |
| `artifacts/<session>/<name>` | the newest version of each file a session attached, with the metadata `version` and `turn` | permanent |
| `tmp/<session>/<path>` | the files a session wrote in `/tmp` and in its project | 7 days |
| `relay/<call>/…` | the parts of one answer on the way to the browser | 1 day |
| `outbox/<id>.bundle` | the commits a session publishes | 1 day |
| `repo/HEAD`, `repo/snapshots/<commit>.tar.gz` | the commit of `main` at the last fetch; one snapshot per fetched commit | permanent; 30 days |

The bucket also keeps each old version of an object for 7 days. EFS holds `releases/<commit>`, `CURRENT` and `work/<commit>[-<run>]`. Vis keeps each version of an attached file in the session, so the transcript shows the file and a checkpoint holds it.

## Functional requirements

### Runtime, lease and state

- FR-1: One container image based on Amazon Linux 2023, with no Lambda base image and no runtime interface client, holds all the code and starts with `/opt/vis/vis-agent-python/python/bin/python3 -m playground`, and `VIS_ROLE` selects which of the five functions the invocation runs.
- FR-2: `playground/runtime.py` speaks the Lambda Runtime API with the standard library and returns both plain answers and streamed answers.
- FR-3: A worker is one invocation of the `worker` function, and only one worker is active at a time, named in `lease.json` with its last checkpoint and the work that waits.
- FR-4: A worker takes `lease.json` with a conditional write, saves a checkpoint of the Vis home directory to `state/<worker>/<n>.tar.gz` when that directory changed, names the checkpoint in the lease with a second conditional write, and then deletes the earlier checkpoint.
- FR-5: A worker that lost the lease cannot replace newer state, and a worker that stops between the checkpoint upload and the lease write leaves that checkpoint in `state/`, where the lease names the checkpoint that counts, every other object in `state/` can be deleted, and the template has no lifecycle rule for `state/` because such a rule can remove the only checkpoint of a stack that nobody used for some days.
- FR-6: All sessions live in the one home directory, so the stack holds many sessions and each new worker gets them all.
- FR-7: `front` sends each call to the worker through SQS, streams the answer from `relay/<call>/…` in S3, and starts a worker when work waits.
- FR-8: A worker reads `CURRENT` at its start and gives its sessions a clone of that release in `work/<commit>`, and each new workflow run reads `CURRENT` again and gets a clone of the newest release in `work/<commit>-<run>`.
- FR-9: The worker removes a project directory that nothing changed for 14 days.

### Release pipeline

- FR-10: A call of `POST /hooks/github` whose GitHub signature is valid starts `repo`, and a schedule also starts `repo` each 15 minutes.
- FR-11: `repo` clones `main` with the deploy key, writes `repo/snapshots/<commit>.tar.gz` and records the commit of `main` at the last fetch in `repo/HEAD`.
- FR-12: `sync` extracts a snapshot into a hidden directory and renames it to `releases/<commit>`, then writes a new `CURRENT` file and renames it over the old one, so that a reader sees the old release or the new release and never a part of one.
- FR-13: `sync` keeps the 5 newest releases on EFS.

### Pages

- FR-14: The pages work on a phone and on a desktop and use no framework and no build step.
- FR-15: `/` serves Vis web with the provider of the stack, and `/play/architecture` shows the design with diagrams.
- FR-16: `/play` shows the sessions and their Vis activities and lets a person download a transcript, fork from a turn or from an artifact, and publish the work.
- FR-17: `/play/workflows` shows the workflow editor with Python highlighting, the workflow activity dialog and the runs, and a waiting run shows where to give its file.
- FR-18: `/play/factory` shows the stations of `software_factory` as a line, a drop zone for the README, the SPEC with its GitHub commit and the earlier orders, and dropping the README on the drop zone starts an order whose stations the page then shows.

### Model calls

- FR-19: `llm` accepts `GET /models` and `POST /chat/completions`, adds the provider key, streams the answer, and refuses a model that is not in `VIS_MODELS`.
- FR-20: A worker sends its model calls to `llm` and has no provider key and no route to the provider.

### Workflows and runs

- FR-21: A workflow is one Python file with exactly one `@workflow` function, whose arguments after `ctx` are the inputs of a run and whose `model` selects the model of the session.
- FR-22: One run is one Vis session, and `POST runs` with `{workflow, input}` starts it while `GET runs/<id>` returns its workflow activities, its source and its artifacts.
- FR-23: When a worker stops in the middle of a run, the next worker starts the run again and each completed workflow activity returns its recorded result from `runs/<run>/results/<n>.json`.
- FR-24: A worker stops 90 seconds before the Lambda time limit, parks the turn that runs, and the gateway of the next worker continues that turn; because the run records the number of session turns before each request, the new run process waits for that turn and sends no second request.
- FR-25: `POST runs/<id>/cancel` cancels a run and the turn of its session.
- FR-26: `ctx.ask(request, Model)` calls `Session.run(request, response_model=Model)` and returns a validated Pydantic object that the workflow branches on, and `ctx.ask(request)` returns the text of the answer.
- FR-27: `ctx.document(name, request)` makes the session write and attach the document, reads the files of that turn with `Session.attachments` and returns an `Artifact`, so that the document is in the transcript, in S3 and in the run.
- FR-28: `ctx.ask` and `ctx.document` wait 900 seconds for a turn unless `timeout=` is set, and when a turn attached no file with the name, `ctx.document` sends one more request and then the workflow activity fails.
- FR-29: `ctx.note(text)` adds a line to the log of the run.
- FR-30: A worker copies the six workflows of `workflows/` — `story_to_spec`, `incident_triage`, `lead_qualification`, `repository_review`, `change_and_publish`, `software_factory` — to S3 when S3 has no workflow, and after that the Workflows page edits the copies in S3, so a stack that has workflows gets no new sample from a later image.
- FR-31: `POST workflows/check` with `{source}` returns the description of a source that is not saved, or the syntax error, and `PUT workflows/<name>` saves a workflow that `GET workflows/<name>` then returns with its source.

### A run waits for a person

- FR-32: `ctx.receive(key, …)` gives the run the status `waiting` and ends the run process, and a waiting run holds no worker and no place of the 3 runs that work at the same time.
- FR-33: The API accepts a file for a waiting run only when the run waits for that key, stores it in `runs/<run>/inputs/<key>.json`, starts the run again, and returns it to `ctx.receive` while the activity record keeps only the key, the name and the size.
- FR-34: `GET runs/<id>/inputs/<key>` returns the file a person gave to the run, or `null`.
- FR-35: The Workflows page and the Factory page show where to give the file of a waiting run, and a script can give it with `POST runs/<run>/inputs/<key>`.
### The software factory
- FR-36: `software_factory` takes the one input `product`, the name of the product, and runs five stations: README intake, where `ctx.receive("readme", …)` waits for the README as `.md` or `.txt`; the SPEC, where `ctx.document("SPEC.md", …)` attaches a specification of nine sections with an identifier for each requirement; the quality gate, where `ctx.ask` returns a validated `Inspection` with `verdict` of `pass` or `rework`, `score` from 0 to 100 and `gaps`; the rework, only for the verdict `rework` and at most once, where `ctx.document("SPEC.md", …)` attaches the next version of `SPEC.md`; and the shipment to GitHub, where the session writes the newest `SPEC.md` to the project directory, calls `playground.publish` and `ctx.ask` returns a validated `Shipment` with `branch`, `commit` and `url`, while a person who does not use the page starts a run of the workflow and gives the file through the API.

### Artifacts and temporary files

- FR-37: A document of a session is a native Vis attachment that the model saves with `attach`, lists with `list_attachments()` and reads with `read_attachment(name)`, and the same name again is the next version; the extension adds no tool for documents and its prompt tells the model to use `attach`.
- FR-38: The API copies each new attached file to `artifacts/<session>/<name>` when a page or a workflow lists the artifacts of a session (`Api.mirror` in `playground/api.py`), and the S3 object carries the metadata `version` and `turn` while S3 holds only the newest version of a name.
- FR-39: `GET artifacts?session=<id>` lists each artifact with `name`, `size`, `at`, `turn` and `version`, and `GET artifacts/<session>/<name>` returns one artifact as a download.
- FR-40: The hook after each `python_execution`, `patch` and `shell` operation finds the files that changed in `/tmp` and in the project directory, copies only regular files without following a link, sends them with `POST tmp` to `tmp/<session>/tmp/` and `tmp/<session>/project/`, and the Files tab of a session shows them.
- FR-41: `GET tmp?session=<id>` lists the temporary files of a session and `GET tmp/<session>/<path>` returns one as a download.

### Publishing to GitHub

- FR-42: `playground.publish(message)` and `POST publish` with `{root, message}` commit a project directory, make a Git bundle of the new commits and put it in `outbox/<id>.bundle`.
- FR-43: `repo` verifies a bundle and pushes it to `main` when `main` did not move, else to a branch `playground/<id>`, and never uses force.
- FR-44: A publication that repeats with no new commit pushes nothing and makes no branch, and its answer names the branch that has the commits and has `pushed` false.
- FR-45: `repo` refuses a push that changes the directory `.github`.
- FR-46: A session can thus change `main`, a release is a copy of `main`, and no person reviews a publication first.

### Scripts outside the stack

- FR-47: `decide.py` runs on a computer with the stack as its Vis gateway, has a session read an invoice and return a validated `Review`, applies the payment policy in Python to select one of three next steps, and for `reject` reads the reply to the vendor with `session.attachments(-1)`; it runs as `PLAYGROUND_URL=… PLAYGROUND_PASSWORD=… uv run --with vis-agent==0.5.18 python decide.py`.
- FR-48: `front` ends an event stream after 870 seconds and a worker ends its streams when it stops; `Turn.wait` and `Session.run` of SDK 0.5.18 connect again until their `timeout`, raise `TransportError` only when repeated connections bring no new event, and the turn continues in the stack so that `session.turns()` or a further `wait` shows it.

### Deployment
- FR-49: `deploy.sh` needs the AWS CLI version 2 with credentials that can make the stack, the GitHub CLI signed in with admin rights for the repository, and `git`, `ssh-keygen`, `jq`, `openssl` and Docker or Podman.

- FR-50: `deploy.sh` is safe to run again and makes the private repository from `repo-seed/` if GitHub does not have it, turns off GitHub Actions for it and adds the ruleset "main is append-only" when the GitHub plan permits a ruleset.
- FR-51: `deploy.sh` builds the image, pushes it to Amazon ECR which keeps the 5 newest images, stores the password, the webhook secret and the deploy key in the Parameter Store, gives GitHub the public half of the deploy key with write access, deploys `template.yaml`, adds the webhook, starts the first fetch and prints the address of the stack and the command that reads the password.
- FR-52: `deploy.sh` keeps each secret that exists, and to change one a person writes `/<stack>/llm-url`, `/<stack>/llm-key` or `/<stack>/password` with `aws ssm put-parameter --overwrite`, which `llm` reads when a new instance starts and `front` after 5 minutes.
- FR-53: `deploy.sh` reads `REPOSITORY`, `PLAYGROUND_LLM_URL` (which must use `https`), `PLAYGROUND_LLM_KEY`, `PLAYGROUND_MODELS` (default `glm-5.3`, `gpt-oss-120b`, `qwen3.8-max`), `STACK` (default `vis-playground`), `AWS_REGION` (default `eu-central-1`) and `ENGINE` (`docker` or `podman`, default `docker`), and gives the model list to the functions as `VIS_MODELS`.
- FR-54: Removing the stack means deleting it in CloudFormation, which also deletes the EFS file system with each project directory, then emptying and deleting the bucket, deleting the ECR repository and the parameters `/<stack>/*`, and removing the webhook, the deploy key and the ruleset from the repository.
- FR-55: `python -m playground.local` runs all five functions in one process with directories in place of S3, EFS and GitHub and a list in place of SQS, serves on `PORT` (default 8080), keeps its data in `PLAYGROUND_LOCAL` (default `/tmp/local`), starts the repository from `PLAYGROUND_SEED` (default `/opt/playground/repo-seed`) and reads the model list from `VIS_MODELS`; it is for development only, because nothing isolates the provider key there and its data in `/tmp/local` goes away with the container.
### Image and repository files
- FR-56: The `Dockerfile` holds the Vis version and its checksums and builds the image with the Vis extensions of `extensions.yml`, Git, Java, Clojure, the Maven cache and Python 3.13 with pytest and ruff for the project, while `requirements/` lists each Python package of the image with its hash.
- FR-57: The repository also holds `vendor.sh`, which fetches the editor and the fonts of the pages each with its checksum, `known_hosts`, `template.yaml` with the stack, `playground/` with the five functions, `extension/` with the Vis extension, `workflows/` with the first workflows, `web/` with the pages, `repo-seed/` with the first content of the repository, `decide.py`, and `ruff.toml`, which sets the format of the Python code to the rules of the repository with lines of at most 200 characters.


## Security requirements

- SR-1: Only the `llm` role can read the provider key, and the worker has no SSM permission and no route to SSM.
- SR-2: `llm` accepts only its two calls and only the models of the stack.
- SR-3: The network of the worker has no internet gateway and no NAT gateway, its resolver answers only for `amazonaws.com` names, and each endpoint accepts only the resources of this stack.
- SR-4: Only `repo` holds a key, that key is a deploy key that opens only the one repository, and `repo` accepts only the SSH host keys of GitHub that `known_hosts` lists.
- SR-5: `repo` never uses force, and a push that is not a fast-forward goes to a new branch.
- SR-6: `repo` refuses a push that changes `.github`, `deploy.sh` turns off GitHub Actions for the repository, and Actions must stay off because a workflow on `main` would run the code a session wrote.
- SR-7: `sync` owns `releases/` and `CURRENT`, the worker has another user id on EFS and cannot write there, and a session can write in `work/` but not in a release.
- SR-8: EFS permits a mount only to the two function roles, each through its own access point, and the worker role cannot write `repo/` in the bucket.
- SR-9: The base image has a digest, each file that `curl` downloads has a SHA-256 and each Python package has a hash; the extensions and the Maven artifacts have an exact version but no hash, and the `dnf` packages have neither in the `Dockerfile`.
- SR-10: `front` compares the password in constant time and sets a signed, `HttpOnly`, `SameSite=Strict` cookie that ends after 7 days.
- SR-11: A request that changes data must come from the same origin, the static files are public, and the pages, `/v1/` and `/play/api/` need the password or the cookie.
- SR-12: `front` checks the `X-Hub-Signature-256` of GitHub before it starts a fetch.
- SR-13: Each S3, SQS and Lambda permission of the worker role carries the condition `aws:SourceVpc`, so outside the network of the stack the credentials permit only a write to the log group of the worker.
- SR-14: The bucket keeps each old version of an object for 7 days, and the worker can delete only `state/`, `relay/`, `workflows/` and `tmp/`.
- SR-15: Each relayed answer has a `sandbox` content security policy, `front` passes only a fixed list of answer headers, and the API sends each artifact and each temporary file as plain text and as a download.
- SR-16: The functions have a concurrency limit — 50 for `front`, 5 for `worker`, 20 for `llm`, 1 for `repo`, 1 for `sync` — and a call cannot ask for more output tokens than the limit of the model.
- SR-17: Lambda permits no new kernel namespace, no seccomp filter and no Landlock rule set, so the Vis jail cannot start in a function and the worker runs without it: session code runs as the user of the worker, can read the temporary credentials of the worker role from the worker process, can call the Lambda Runtime API of the worker, and can read and change the data of the other sessions of the stack.
- SR-18: The gateway and the tools of a session have no AWS credentials in their environment, the worker role permits only the bucket prefixes, the queue and the three functions the worker needs, and each secret lives in a function that does not run the code of a session.
- SR-19: One stack is for one team that shares its sessions, each tenant gets its own stack, and the provider key has no spending limit in this stack so a budget must be set for it at the provider.

## Limits

Runs and workflows: at most 3 runs work at the same time while the others wait in the queue and a waiting run uses no place; a run uses at most 12 processes, each worker change and each given file starting a new one; a run has at most 1000 workflow activities; `runs/index.json` holds the 300 newest runs and `GET runs` returns the 100 newest; the name of a workflow and the key of `ctx.receive` have the form `[a-z][a-z0-9_]{1,39}`; a workflow file has exactly one `@workflow` function and at most 200 000 characters; a file for a waiting run is text of at most 300 000 bytes with a name that starts with a letter or a digit and has at most 80 characters from letters, digits, `.`, `_`, `-` and spaces; `ctx.ask` and `ctx.document` wait 900 seconds by default; Vis continues one turn in at most three new workers, so a turn should stay shorter than about 40 minutes.

Files: the API copies an attached file to S3 only when its size is at most 2 000 000 bytes and its name has the form above, and a larger file stays only in the session; the hook copies a written file of at most 1 000 000 bytes, skips `.git`, `__pycache__`, `node_modules`, `.cpcache`, `.venv`, `target`, `.pytest_cache`, `.ruff_cache`, `.clj-kondo` and `.lsp`, and reads at most 20 000 files of a directory; a Git bundle for `repo` has at most 100 000 000 bytes and a commit message at most 200 characters; a model request has at most 5 000 000 bytes and asks for one answer.

Time and cost: `front` waits 55 seconds for the first part of an answer and then answers 504; an event stream ends after 870 seconds and the client connects again; a worker without work stops after 300 seconds and a worker with work gives it to a new worker after 810 seconds; the cookie ends after 7 days and a new password is in effect after 5 minutes; `sync` keeps the 5 newest releases; the worker removes a project directory unchanged for 14 days; CloudWatch keeps the log of each function for 14 days. The stack reserves 77 concurrent executions and the account limit must be 177 or more because AWS keeps 100 for the other functions. When nobody uses it, the only compute is the schedule, which calls `front` each minute and `repo` each 15 minutes, while the two interface endpoints and the EFS file system cost about 20 USD each month and S3 and the 5 images in ECR add their storage cost.

Optional worker and front variables with their defaults: `VIS_IDLE_S` 300, `VIS_LIFETIME_S` 900 (equal to the `Timeout` of the worker in the template), `VIS_HANDOFF_MARGIN_S` 90, `VIS_STREAM_S` 870.

## Acceptance criteria

- AC-1 (FR-4, FR-5, FR-6): With a session in the home directory, a second worker started after the first stops lists that session, and a worker that lost the lease leaves the newer state of the lease holder unchanged.
- AC-2 (FR-10, FR-11, FR-12): A push to `main` produces, within one webhook call or one 15-minute schedule, a snapshot, a directory `releases/<commit>` and a `CURRENT` that names it, and a reader that reads during the change gets either the old or the new release.
- AC-3 (FR-13): After six successful releases, EFS holds exactly the 5 newest `releases/<commit>` directories.
- AC-4 (FR-14 to FR-18): A browser at a phone width and at a desktop width renders all four pages, and `GET /play/factory` without the password returns the sign-in page while the same call with a valid `Authorization: Bearer <password>` returns the factory page.
- AC-5 (SR-10, SR-11, FR-1): `POST /login` with the password returns a cookie that is signed, `HttpOnly` and `SameSite=Strict` and that stops working after 7 days, and a data-changing browser request from another origin is refused.
- AC-6 (SR-12): `POST /hooks/github` with a wrong or missing `X-Hub-Signature-256` starts no fetch.
- AC-7 (FR-19, SR-2): `POST /chat/completions` with a model outside `VIS_MODELS` is refused, and a model name in the list returns a streamed answer.
- AC-8 (FR-23, FR-24): A run killed in the middle of activity 3 finishes on the next worker with the recorded results of activities 1 and 2, no second request for the parked turn, and no more than 12 processes in total.
- AC-9 (FR-27, FR-28): `ctx.document("SPEC.md", …)` returns an `Artifact` whose name, session, size and version match the attachment of that turn, and when the turn attaches no `SPEC.md` the activity sends exactly one more request and then fails.
- AC-10 (FR-32, FR-33, Limits): A run in `waiting` holds no worker and no place of the 3 concurrent runs; `POST runs/<id>/inputs/<key>` with the key the run waits for restarts it and `ctx.receive` returns that file, while a post to another key or a body over 300 000 bytes is refused.
- AC-11 (FR-37 to FR-39): After a session attaches `SPEC.md` twice and a page lists the artifacts, `GET artifacts?session=<id>` shows one entry for `SPEC.md` with `version` 2 and its `turn`, `GET artifacts/<session>/SPEC.md` downloads it as plain text, and the copy appears in S3 only when the size is at most 2 000 000 bytes.
- AC-12 (FR-40, FR-41): A `python_execution` that writes a file in `/tmp` and in the project makes both appear under `tmp/<session>/…` and in the Files tab, while a symbolic link, a file over 1 000 000 bytes and a file in `.git` do not appear.
- AC-13 (FR-42 to FR-45, SR-5, SR-6): `POST publish` on an unmoved `main` pushes to `main`, on a moved `main` pushes to `playground/<id>` with `pushed` false on a repeat that adds no commit, and a commit that changes `.github` is refused.
- AC-14 (FR-30, FR-31): On a stack whose bucket has no workflow, a worker writes the six sample workflows to `workflows/`; a later image adds no new sample to a stack that already has them; `POST workflows/check` returns the syntax error of a source that does not compile and saves nothing.
- AC-15 (FR-48, SR-16): A client whose event stream ends after 870 seconds reconnects and receives the further events of the same turn, and `Turn.wait` raises `TransportError` only after repeated connections bring no new event.
- AC-16 (FR-50 to FR-54): `deploy.sh` run twice on the same account leaves the existing secrets unchanged, ends with a reachable stack address, an ECR repository of at most 5 images, GitHub Actions off, the webhook installed and the ruleset present when the plan permits it.
- AC-17 (FR-55): Inside the built image, `python -m playground.local` serves the pages and the API on port 8080 with `/tmp/local` as its data and `repo-seed/` as the first repository content.
- AC-18 (SR-3, SR-13, SR-17): Session code that reads the temporary credentials of the worker role and calls an AWS API from outside the VPC of the stack gets no access except a write to the log group of the worker, and a session inside the worker cannot resolve or reach a host that is not an `amazonaws.com` name of this stack.
- AC-19 (SR-14, Data): After a session deletes or overwrites an object, the earlier version is readable from the bucket for 7 days, and a delete call by the worker outside `state/`, `relay/`, `workflows/` and `tmp/` is refused.
- AC-20 (Limits): A workflow file of 200 001 characters, a workflow with two `@workflow` functions, a name outside `[a-z][a-z0-9_]{1,39}`, a 1001st activity, a 13th process, a Git bundle of 100 000 001 bytes, a commit message of 201 characters and a model request of 5 000 001 bytes are each refused.
- AC-21 (FR-36): A run of `software_factory` started with `product` set, given a README for the key `readme`, ends with an attached `SPEC.md` of nine sections with an identifier for each requirement, a recorded `Inspection` whose `verdict` is `pass` or `rework` and whose `score` is between 0 and 100, at most two versions of `SPEC.md`, and a `Shipment` whose `branch`, `commit` and `url` name that commit on GitHub.
- AC-22 (FR-49, FR-56): Inside the built image `git`, `java`, `clojure`, `pytest` and `ruff` each answer a version call, and `deploy.sh` on a machine that lacks the GitHub CLI, `ssh-keygen`, `jq`, `openssl` or a container engine does not deploy the stack.
