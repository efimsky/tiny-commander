class TinyCommander < Formula
  desc "Zero-dependency dual-pane file manager for restricted environments"
  homepage "https://github.com/efimsky/tiny-commander"
  head "https://github.com/efimsky/tiny-commander.git", branch: "main"

  depends_on "python@3.13"

  def install
    # Install the package using pip without dependencies (there are none)
    system "python3.13", "-m", "pip", "install", *std_pip_args, "."
  end

  test do
    # Simple smoke test
    assert_match "tiny-commander", shell_output("#{bin}/tnc --help 2>&1", 1)
  end
end
