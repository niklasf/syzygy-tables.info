$(function () {
  var board, chess = new Chess('4k3/8/8/8/8/8/8/4K3 w - - 0 1');

  var $info = $('#info');
  var $status = $('#status');
  var $winning = $('#winning');
  var $drawing = $('#drawing');
  var $losing = $('#losing');

  function probe(fen) {
    var tmpChess = new Chess(fen);

    if (fen == '4k3/8/8/8/8/8/8/4K3 w - - 0 1') {
      $status.text('Draw by insufficient material').removeClass('black-win').removeClass('white-win');
      $info.html('<p>Syzygy tablebases provide win-draw-loss and distance-to-zero information for all endgame positions with up to 6 pieces.</p><p>Minmaxing the DTZ values guarantees winning all winning positions and defending all drawn positions.</p><p><strong>Setup a position on the board to probe the tablebases.</strong></p>');
      return;
    } else if (fen == 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1') {
      $status.text('Position not found in tablebases').removeClass('black-win').removeClass('white-win');
      $info.html('<p><a href="https://en.wikipedia.org/wiki/Solving_chess">Chess is not yet solved.</a></p>');
    } else if (tmpChess.in_checkmate()) {
      if (tmpChess.turn() == 'b') {
        $status.text('White won by checkmate').removeClass('black-win').addClass('white-win');
      } else {
        $status.text('Black won by checkmate').removeClass('white-win').addClass('black-win');
      }
      $info.empty();
      return;
    } else if (tmpChess.in_stalemate()) {
      $status.text('Draw by stalemate').removeClass('black-win').removeClass('white-win');
      $info.empty();
      return;
    }

    $status.text('Loading ...');
    $info.html('<div class="spinner"><div class="double-bounce1"></div><div class="double-bounce2"></div></div>');
    $winning.empty();
    $drawing.empty();
    $losing.empty();

    $.ajax('/api', {
      data: {
        'fen': fen,
      },
      error: function (xhr, textStatus, errorThrown) {
        if (xhr.status == 400) {
          $status.text('Invalid position').removeClass('black-win').removeClass('white-win');
          $info.html('<p>The given position is not a legal chess position.</p>');
        } else {
          // TODO: Add retry button
          $status.text('Network error').removeClass('black-win').removeClass('white-win');
          $info.text('Request failed: ' + textStatus);
        }
      },
      success: function (data) {
        if (tmpChess.insufficient_material()) {
          $status.text('Draw by insufficient material').removeClass('black-win').removeClass('white-win');
          $info.html('<p><strong>The game is drawn</strong> because with the remaining material no sequence of legal moves can lead to a checkmate.</p>');
          return;
        }
      }
    });
  }

  board = new ChessBoard('board', {
    position: $('#board').attr('data-fen'),
    pieceTheme: '/static/chesspieces/wikipedia/{piece}.png',
    draggable: true,
    dropOffBoard: 'trash',
    sparePieces: true,
    onDrop: function (source, target, piece, newPos, oldPos, orientation) {
      if (source != 'spare' && target != 'trash' && chess.move({ from: source, to: target })) {
        $btn_white.toggleClass('active', chess.turn() == 'w');
        $btn_black.toggleClass('active', chess.turn() == 'b');
        var parts = chess.fen().split(/ /);
        parts[4] = '0';
        parts[5] = '1';
        var fen = parts.join(' ');
        $fen.val(fen);
        probe(fen);
      } else {
        var fen = ChessBoard.objToFen(newPos) + ' ' + ($btn_white.hasClass('active') ? 'w' : 'b') + ' - - 0 1';
        $fen.val(fen);
        chess.load(fen);
        probe(fen);
      }
    }
  });

  var $btn_white = $('#btn-white');
  var $btn_black = $('#btn-black');
  var $fen = $('#fen');

  $btn_white.click(function (event) {
    event.preventDefault();
    var fen = board.fen() + ' w - - 0 1';
    chess.load(fen);
    $fen.val(fen);
    $btn_white.addClass('active');
    $btn_black.removeClass('active');
    probe(fen);
  });

  $btn_black.click(function (event) {
    event.preventDefault();
    var fen = board.fen() + ' b - - 0 1';
    chess.load(fen);
    $fen.val(fen);
    $btn_white.removeClass('active');
    $btn_black.addClass('active');
    probe(fen);
  });

  $('#form-set-fen').submit(function (event) {
    event.preventDefault();

    var parts = $fen.val().trim().split(/\s+/);
    if (parts.length == 1) {
      parts.push($btn_white.hasClass('active') ? 'w' : 'b');
    }
    if (parts.length == 2) {
      parts.push('-');
    }
    if (parts.length == 3) {
      parts.push('-');
    }
    if (parts.length == 4) {
      parts.push('0');
    }
    if (parts.length == 5) {
      parts.push('1');
    }

    var fen = parts.join(' ');
    if (!chess.load(fen)) {
      fen = '4k3/8/8/8/8/8/8/4K3 w - - 0 1';
      chess.load(fen);
    }

    board.position(fen);
    $fen.val(fen);
    probe(fen);
  });
});
