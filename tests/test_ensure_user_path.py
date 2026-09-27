"""make install adds ~/bin to the default shell rc file when it is missing."""
from __future__ import annotations

import scripts.ensure_user_path as pathrc


def test_bash_is_the_rc_for_the_bash_shell(tmp_path):
    """A bash login shell is updated in ~/.bashrc."""

    # Given a home whose bashrc does not mention ~/bin
    home = tmp_path / "home"
    home.mkdir()

    # When install ensures the path for /bin/bash
    result = pathrc.ensure_bin_on_path(home, "/bin/bash")

    # Then the export is at the top of .bashrc
    text = (home / ".bashrc").read_text()
    assert result == "added"
    assert text.startswith('export PATH="$HOME/bin:$PATH"\n')


def test_zsh_is_the_rc_for_the_zsh_shell(tmp_path):
    """A zsh login shell is updated in ~/.zshrc, not bashrc."""

    # Given an empty home and a zsh shell
    home = tmp_path / "home"
    home.mkdir()

    # When install ensures the path for zsh
    result = pathrc.ensure_bin_on_path(home, "/usr/bin/zsh")

    # Then only .zshrc is written
    assert result == "added"
    assert (home / ".zshrc").read_text().startswith('export PATH="$HOME/bin:$PATH"\n')
    assert not (home / ".bashrc").exists()


def test_existing_home_bin_line_is_left_alone(tmp_path):
    """A second install does not duplicate the PATH line."""

    # Given a bashrc that already exports ~/bin, with other lines after it
    home = tmp_path / "home"
    home.mkdir()
    rc = home / ".bashrc"
    rc.write_text('export PATH="$HOME/bin:$PATH"\n# keep me\n')

    # When install ensures the path again
    result = pathrc.ensure_bin_on_path(home, "/bin/bash")

    # Then the file is unchanged
    assert result == "already"
    assert rc.read_text() == 'export PATH="$HOME/bin:$PATH"\n# keep me\n'


def test_line_is_inserted_before_an_early_return(tmp_path):
    """The export runs even when the rc returns for non-interactive shells."""

    # Given a bashrc that returns before any later setup
    home = tmp_path / "home"
    home.mkdir()
    (home / ".bashrc").write_text('[[ $- != *i* ]] && return\nalias ll=ls\n')

    # When install ensures the path
    pathrc.ensure_bin_on_path(home, "/usr/bin/bash")

    # Then the export is the first line
    lines = (home / ".bashrc").read_text().splitlines()
    assert lines[0] == 'export PATH="$HOME/bin:$PATH"'
    assert lines[1] == "[[ $- != *i* ]] && return"
