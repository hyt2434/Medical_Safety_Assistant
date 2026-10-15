# Medicine Assistant -- Project Proposal LaTeX template

This reusable template follows the PA0 proposal requirements:

1. Team Members / Thành viên nhóm
2. Introduction
3. Target Users and Environments
4. Key Features
5. Potential-user Interviews and Evidence (at least five people)
6. References

## Fill in the report

1. Edit project, course, group, submission, header, and footer data in
   `config/metadata.tex`. The four header/footer fields are independent from
   the project name; set a field to `{}` if you want it blank.
2. Replace gray placeholders in `pages/01-team-members.tex` through `pages/06-references.tex`.
3. Put report images in `images/` and include them with `\includegraphics`.
4. Check that teaching staff can access every interview evidence link.

Find unfinished fields before submission:

```powershell
rg "\\placeholder" config pages
```

## Build

Run twice from `docs/latex` so the table of contents is updated:

```powershell
pdflatex -interaction=nonstopmode -halt-on-error main.tex
pdflatex -interaction=nonstopmode -halt-on-error main.tex
```

`main.tex` is the only entry point. Generated `.aux`, `.log`, `.out`, and
`.toc` files are build artifacts; do not edit them.
