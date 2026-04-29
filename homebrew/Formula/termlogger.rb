class Termlogger < Formula
  desc "Terminal-based amateur radio logging application"
  homepage "https://github.com/lacy-digital-labs/TermLogger"
  version "26.01.03"
  license "MIT"

  on_macos do
    on_arm do
      url "https://github.com/lacy-digital-labs/TermLogger/releases/download/v#{version}/termlogger-macos-arm64"
      sha256 "4d6a3aa4eb98baccc0adc7043a50960330734a059f6e78b79e4baf8175c5bb69"
    end
    on_intel do
      url "https://github.com/lacy-digital-labs/TermLogger/releases/download/v#{version}/termlogger-macos-x86_64"
      sha256 "ee14ab629ef3eb0e3da435cd736ec3ffebe04daa476f35638e1911a37b80f723"
    end
  end

  def install
    bin.install Dir["termlogger-macos-*"].first => "termlogger"
  end

  test do
    assert_match version.to_s, shell_output("#{bin}/termlogger --version")
  end
end
