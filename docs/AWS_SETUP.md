# AWS Setup (Phase 2) — do these once

Everything here is browser/console work that only you can do. When it's done, the
terminal takes over. Budget ~20 minutes. Cost for this project: effectively $0
(well inside free tier), but AWS still requires a card on file.

> Region: use **us-east-1** (N. Virginia) everywhere unless you have a reason not
> to. Keep it consistent — buckets and CLI config must agree.

---

## 1. Create an AWS account (skip if you already have one)

1. Go to <https://aws.amazon.com/> → **Create an AWS Account**.
2. Email + account name → verify the code they email you.
3. Set a root password.
4. Contact info → choose **Personal** account type.
5. **Add a credit/debit card.** Required even for free tier. We won't incur charges.
6. Phone/SMS identity verification.
7. Choose the **Basic support – Free** plan.
8. Sign in to the **AWS Management Console**.

You're now signed in as the **root user**. Don't make keys for root — make an IAM
user instead (next step). Root is for break-glass only.

> Strongly recommended: enable **MFA on the root user** now.
> Console → click your account name (top right) → **Security credentials** →
> **Multi-factor authentication (MFA)** → add your phone authenticator app.

---

## 2. Create an IAM user with access keys

1. In the console search bar type **IAM** → open it.
2. Left sidebar → **Users** → **Create user**.
3. User name: `turbofan-cli` (anything works).
4. **Do NOT** check "Provide user access to the Management Console" — this user is
   for the CLI only.
5. **Next** → Permissions.

### Attach permissions (start simple)

6. Choose **Attach policies directly**.
7. Search **`AmazonS3FullAccess`** → tick it.
   - This is broad but scoped to S3 only, fine for a sandbox project. We'll
     tighten it to a single bucket later (step 5) as a deliberate exercise.
8. **Next** → **Create user**.

### Generate the access keys

9. Click the new user → **Security credentials** tab.
10. Scroll to **Access keys** → **Create access key**.
11. Use case: **Command Line Interface (CLI)** → tick the confirmation box → **Next**.
12. (Optional description) → **Create access key**.
13. You now see **Access key ID** and **Secret access key**.
    - **Copy both now** (or "Download .csv"). The secret is shown **once** — if you
      lose it, delete the key and make a new one. No big deal, just redo this step.

**Never paste these keys into chat, a file in the repo, or git.** They go in exactly
one place: `aws configure` (next).

---

## 3. Configure the CLI (in your terminal)

First make sure the AWS CLI is installed:

```
aws --version
```

If "command not found": `brew install awscli`.

Then, in this Claude session, run it yourself with the `!` prefix so the prompts
work interactively:

```
! aws configure
```

It asks four things — paste/enter:

| Prompt                  | Value                                    |
|-------------------------|------------------------------------------|
| AWS Access Key ID       | *(paste the key id)*                     |
| AWS Secret Access Key   | *(paste the secret)*                     |
| Default region name     | `us-east-1`                              |
| Default output format   | `json`                                   |

This writes `~/.aws/credentials` and `~/.aws/config`. These live in your home
directory, **not** the repo, so they're never committed.

---

## 4. Hand back to the terminal

Tell me when step 3 is done. I'll verify with:

```
aws sts get-caller-identity      # confirms which IAM user the CLI is acting as
```

…then create the bucket + prefixes, wire the `--s3` flag into the pipeline, upload
the data, and run it end-to-end against S3.

---

## 4b. Deploy identity for the API (Phase 2.4)

The runtime user `turbofan-cli` is intentionally S3-only. Deploying the
predictions API needs Lambda + API Gateway + IAM-role powers, so we make a
**separate deploy identity** rather than handing those powers to the runtime keys.
(Separating "what runs the pipeline" from "what deploys infrastructure" is a real
best practice — and a clean thing to explain in an interview.)

1. IAM console → **Users** → **Create user** → name `turbofan-admin`.
2. No console access (CLI only).
3. **Attach policies directly** → tick these three managed policies:
   - `AWSLambda_FullAccess`
   - `AmazonAPIGatewayAdministrator`
   - `IAMFullAccess`  *(needed to create + pass the Lambda execution role)*
4. Create the user → **Security credentials** → **Create access key** → **CLI** →
   copy the key id + secret.
5. Configure it as a **named profile** (keeps it separate from `turbofan-cli`):

   ```
   ! aws configure --profile turbofan-admin
   ```

   Same four prompts (key, secret, `us-east-1`, `json`).

6. Tell Claude it's ready. Deploy runs under that profile:

   ```
   AWS_PROFILE=turbofan-admin python api/deploy.py
   ```

7. **When Phase 2 is done you can delete this user's access keys** — you only need
   them while actively deploying infra. The runtime pipeline never uses them.

---

## 5. (Later) Tighten to least privilege — the interview-friendly version

Once the bucket exists and the pipeline works on S3FullAccess, we swap the broad
policy for one scoped to just our bucket. This is the "I started broad, then locked
it down" story interviewers like. I'll generate the JSON; the swap is:
detach `AmazonS3FullAccess` → attach the inline scoped policy. Done later, together.
