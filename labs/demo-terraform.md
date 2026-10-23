# Demo: Terraform (Trainer)

**Ziel:** Bucket und ETL-Benutzer entstehen aus Code statt aus Klicks. Der Trainer plant, wendet
an, ändert und baut wieder ab.

**Dauer:** rund 10 Minuten als Vorführung. Wer will, macht es nach dem Kurs selbst nach.

**Voraussetzung:** Terraform (oder OpenTofu, Befehl `tofu`) ist installiert, floci läuft
aus Lab 3 auf Port 4566.

## 1. Ordner anlegen

```bash
git switch -c terraform
mkdir terraform && cd terraform
```

## 2. `provider.tf`: wohin Terraform spricht

```hcl
terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

provider "aws" {
  region     = "eu-central-1"
  access_key = "test"
  secret_key = "test"

  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true
  s3_use_path_style           = true

  endpoints {
    s3  = "http://localhost:4566"
    iam = "http://localhost:4566"
    sts = "http://localhost:4566"
  }
}
```

## 3. `variables.tf`

```hcl
variable "umgebung" {
  description = "Name der Umgebung, wird an alle Namen angehängt"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "test", "prod"], var.umgebung)
    error_message = "Erlaubt sind dev, test und prod."
  }
}

variable "versionierung" {
  description = "Alte Fassungen von Dateien im Bucket aufbewahren"
  type        = bool
  default     = true
}
```

## 4. `main.tf`: was es geben soll

```hcl
locals {
  bucket = "viertelwatt-rohdaten-${var.umgebung}"
}

resource "aws_s3_bucket" "rohdaten" {
  bucket = local.bucket

  tags = {
    projekt  = "viertelwatt"
    umgebung = var.umgebung
  }
}

resource "aws_s3_bucket_versioning" "rohdaten" {
  bucket = aws_s3_bucket.rohdaten.id

  versioning_configuration {
    status = var.versionierung ? "Enabled" : "Suspended"
  }
}

resource "aws_iam_user" "etl" {
  name = "etl-job-${var.umgebung}"
}

resource "aws_iam_user_policy" "rohdaten_lesen" {
  name = "rohdaten-lesen"
  user = aws_iam_user.etl.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "BucketAuflisten"
        Effect   = "Allow"
        Action   = "s3:ListBucket"
        Resource = aws_s3_bucket.rohdaten.arn
      },
      {
        Sid      = "RohdatenLesen"
        Effect   = "Allow"
        Action   = "s3:GetObject"
        Resource = "${aws_s3_bucket.rohdaten.arn}/*"
      }
    ]
  })
}
```

## 5. `outputs.tf`

```hcl
output "bucket_name" {
  description = "Name des Rohdaten-Buckets"
  value       = aws_s3_bucket.rohdaten.bucket
}

output "bucket_arn" {
  value = aws_s3_bucket.rohdaten.arn
}

output "etl_benutzer" {
  value = aws_iam_user.etl.name
}
```

## 6. Init, Plan, Apply

```bash
terraform init
terraform fmt
terraform validate
terraform plan
```

Kontrolle: `Plan: 4 to add, 0 to change, 0 to destroy.` Noch ist nichts passiert.

```bash
terraform apply
aws s3 ls
terraform output
```

Kontrolle: Der Bucket `viertelwatt-rohdaten-dev` ist da, `terraform output` zeigt Name und ARN.

## 7. Noch einmal anwenden

```bash
terraform apply
```

Kontrolle: `No changes. Your infrastructure matches the configuration.` Das ist der Kern
von Infrastructure as Code: Der Code beschreibt einen Zustand, nicht eine Handlung.

> Will Terraform beim zweiten Mal die `tags` des Buckets ändern, speichert der Emulator die
> Tags nicht vollständig. Gegen echtes AWS tritt das nicht auf. Gut zu wissen: Ein Emulator
> ist nah an AWS, aber nicht AWS.

## 8. Den State ansehen

```bash
terraform state list
terraform state show aws_s3_bucket.rohdaten
```

Kontrolle: Vier Ressourcen. Der State ist Terraforms Gedächtnis darüber, was es angelegt hat.

## 9. Eine Änderung planen

Lege `test.tfvars` an:

```hcl
umgebung      = "test"
versionierung = false
```

```bash
terraform plan -var-file=test.tfvars
```

Kontrolle: Am Ende steht `Plan: 3 to add, 1 to change, 3 to destroy.` Finde im Plan die vier
Ressourcen, aus denen sich diese Zahlen ergeben:

| Ressource | Was der Plan sagt | Warum |
|---|---|---|
| `aws_s3_bucket.rohdaten` | `must be replaced` | Ein Bucketname lässt sich nicht ändern |
| `aws_s3_bucket_versioning.rohdaten` | `must be replaced` | Sie hängt am alten Bucket |
| `aws_iam_user_policy.rohdaten_lesen` | `must be replaced` | Sie hängt am Benutzernamen |
| `aws_iam_user.etl` | `will be updated in-place` | Einen IAM-Benutzer kann AWS umbenennen |

Bei den ersetzten Ressourcen markiert der Plan das auslösende Attribut mit
`# forces replacement`. Wende diesen Plan **nicht** an. Warum wäre das in einem echten
Projekt gefährlich?

## 10. Abbauen

```bash
terraform destroy
aws s3 ls
```

Kontrolle: `viertelwatt-rohdaten-dev` ist weg. `viertelwatt-rohdaten` aus Lab 3 ist noch da,
weil Terraform nur abbaut, was in seinem State steht.

## 11. Festhalten

```bash
cd ..
git add terraform/*.tf terraform/test.tfvars terraform/.terraform.lock.hcl
git status   # terraform.tfstate darf NICHT dabei sein
git commit -m "Terraform: Rohdaten-Bucket und ETL-Benutzer"
git push -u origin terraform && gh pr create --fill
gh pr checks --watch
gh pr merge --merge --delete-branch
git switch main && git pull
```
