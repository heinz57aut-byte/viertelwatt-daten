# Lab 1: Git und GitHub

**Ziel:** Du versionierst Änderungen mit Git, arbeitest auf einem Branch und bringst eine
Änderung über einen Pull Request in den Hauptzweig.

**Dauer:** rund 55 Minuten, davon 15 für das GitHub-Konto

**Voraussetzung:** Git und die GitHub CLI `gh` sind installiert. Das GitHub-Konto legst du in
Teil B an.

## Teil A: Git lokal kennenlernen

### 1. Einmalig: Wer bist du?

```bash
git config --global user.name "Vorname Nachname"
git config --global user.email "deine-adresse@example.com"
git config --global init.defaultBranch main
git config --global pull.rebase false
git config --global core.editor nano
```

| Einstellung | Warum |
|---|---|
| `user.name`, `user.email` | Git schreibt in jeden Commit, wer ihn gemacht hat. Ohne Angabe verweigert Git den Commit oder trägt den Rechnernamen ein |
| `init.defaultBranch main` | Ohne sie heißt der erste Branch `master`. GitHub und die Pipeline erwarten `main` |
| `pull.rebase false` | `git pull` führt auseinandergelaufene Stände zusammen, statt mit `Need to specify how to reconcile divergent branches` abzubrechen |
| `core.editor nano` | Braucht Git einen Text von dir, öffnet es `nano` statt `vim`. Speichern mit Strg+O und Enter, beenden mit Strg+X |
| `--global` | Gilt für alle Repositorys deines Benutzers, steht in `~/.gitconfig`. Einmal je Rechner |

> Dein Repository wird öffentlich. Die Adresse aus `user.email` steht in jedem Commit und
> ist für alle lesbar. Nimm die noreply-Adresse von GitHub, sobald du in Schritt 6 dein Konto
> hast, und setze sie dann mit demselben Befehl neu.

Kontrolle: `git config --global --list` zeigt Name, Adresse, `init.defaultbranch=main`,
`pull.rebase=false` und `core.editor=nano`.

### 2. Ein Repository anlegen

```bash
mkdir ~/git-uebung
cd ~/git-uebung
git init
git status
```

Kontrolle: `git status` meldet `On branch main` und `No commits yet`. Ist dein System auf
Deutsch eingestellt, steht dort `Auf Branch main` und `Noch keine Commits`.

### 3. Der erste Commit

```bash
echo "Auswertung Oktober" > notiz.txt
git status          # notiz.txt ist "untracked" (deutsch: "unversioniert")
git add notiz.txt
git status          # jetzt "staged" (deutsch: "zum Commit vorgemerkt")
git commit -m "Notiz zur Oktoberauswertung angelegt"
git log --oneline
```

Kontrolle: `git log --oneline` zeigt genau einen Eintrag mit einer kurzen Kennung vorne.

### 4. Eine Änderung ansehen und festhalten

```bash
echo "Quelle: Netzbetreiber, Viertelstundenwerte" >> notiz.txt
git diff            # was hat sich geändert, noch nicht gestaged
git add notiz.txt
git diff --staged   # was kommt in den nächsten Commit
git commit -m "Datenquelle ergaenzt"
git log --oneline
```

Kontrolle: Zwei Commits. `git show HEAD` zeigt die hinzugefügte Zeile mit `+` davor.

### 5. Was nicht ins Repository gehört

```bash
echo "DB_PASSWORT=geheim" > .env
echo ".env" >> .gitignore
git status
```

Kontrolle: `git status` zeigt `.gitignore`, aber **nicht** `.env`. Committe `.gitignore`.

## Teil B: Mit GitHub arbeiten

### 6. Dein GitHub-Konto

Lege auf [github.com/signup](https://github.com/signup) ein Konto an und bestätige die
E-Mail-Adresse. Dann im Browser:

- **Settings › Emails:** **Keep my email addresses private** einschalten. Darunter steht
  deine noreply-Adresse der Form `12345678+name@users.noreply.github.com`.
- Dieselbe Seite: **Block command line pushes that expose my email** einschalten.
- **Settings › Password and authentication:** Zwei-Faktor-Anmeldung mit einer
  Authenticator-App einrichten. GitHub verlangt sie früher oder später ohnehin.

Dann im Ubuntu-Terminal:

```bash
git config --global user.email "12345678+name@users.noreply.github.com"
gh auth login
gh auth status
```

Bei `gh auth login`: **GitHub.com**, **HTTPS**, Git mit GitHub-Anmeldung verbinden **Ja**,
Anmeldung über den **Browser**. Öffnet sich kein Browser, rufe `github.com/login/device` im
Windows-Browser auf und gib den angezeigten Code ein.

Kontrolle: `gh auth status` zeigt `Logged in to github.com account <dein-name>`.

### 7. Die Kursdateien holen

Lade aus Moodle die Datei `viertelwatt-daten.zip` herunter. Unter Windows landet sie im
Windows-Ordner Downloads, den du in Ubuntu unter `/mnt/c/Users/<dein-windows-name>/Downloads`
erreichst. Unter macOS liegt sie in `~/Downloads`.

```bash
cd ~
ls /mnt/c/Users/
cp /mnt/c/Users/<dein-windows-name>/Downloads/viertelwatt-daten.zip ~
```

`ls /mnt/c/Users/` zeigt deinen Windows-Namen. Unter macOS lautet die zweite Zeile
`cp ~/Downloads/viertelwatt-daten.zip ~`, die erste entfällt.

Kontrolle: `ls ~` zeigt `viertelwatt-daten.zip`.

### 8. Entpacken und das Repository anlegen

```bash
cd ~
unzip -q viertelwatt-daten.zip
cd viertelwatt-daten
git init
git add .
git commit -m "Kursdateien aus Moodle"
gh repo create viertelwatt-daten --public --source=. --push
```

- `cd ~` zuerst: Sonst landet das Übungsrepo im Ordner `git-uebung` aus Teil A, ein
  Repository im Repository.
- `gh repo create … --source=. --push` legt das Repository auf GitHub an, trägt es als
  `origin` ein und lädt deinen Commit hoch.

> Öffentlich, weil GitHub Actions und die Container Registry für öffentliche Repositories
> ohne Kontingent nutzbar sind. Es liegen keine echten Daten darin.

Kontrolle: `git remote -v` zeigt `origin` mit der Adresse deines Repositories,
`git log --oneline` genau einen Commit.

### 9. Auf einem Branch arbeiten

```bash
git switch -c team-eintragen
```

Trage in `README.md` in der Tabelle **Team** deinen Namen und deinen GitHub-Namen ein. Öffne
die Datei dafür mit `code README.md` (VS Code) oder `nano README.md`.

```bash
git add README.md
git commit -m "Team: eigenen Namen eingetragen"
git push -u origin team-eintragen
```

Kontrolle: Die Ausgabe von `git push` enthält einen Link `Create a pull request`.

### 10. Pull Request und Merge

```bash
gh pr create --fill
gh pr view --web
```

Sieh dir im Browser den Reiter **Files changed** an. Dann:

```bash
gh pr merge --merge --delete-branch
git switch main
git pull
git log --oneline --graph
```

Kontrolle: `git log --graph` zeigt deinen Commit und einen Merge-Commit auf `main`.

## Zusatz für Schnelle: einen Konflikt erzeugen und lösen

1. Ändere auf GitHub im Browser die erste Zeile von `README.md` und committe dort.
2. Ändere lokal dieselbe Zeile anders und committe.
3. `git pull` meldet `CONFLICT (content): Merge conflict in README.md`. Öffne die Datei,
   entferne die Markierungen `<<<<<<<`, `=======` und `>>>>>>>`, entscheide dich für eine
   Fassung. Kommt stattdessen `Need to specify how to reconcile divergent branches`, fehlt
   die Einstellung `pull.rebase false` aus Schritt 1.
4. `git add README.md`, `git commit --no-edit`, `git push`. `--no-edit` übernimmt die
   vorgeschlagene Nachricht für den Merge-Commit, ohne einen Editor zu öffnen.
