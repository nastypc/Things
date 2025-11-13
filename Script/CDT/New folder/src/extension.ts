import * as vscode from 'vscode';

export function activate(context: vscode.ExtensionContext) {
  console.log('CDT Hover Converter extension activated!');
  
  // Register hover provider for all files, but only activate for .cdt files
  const hoverProvider = vscode.languages.registerHoverProvider('*', {
    provideHover(document: vscode.TextDocument, position: vscode.Position, token: vscode.CancellationToken): vscode.ProviderResult<vscode.Hover> {
      // Only provide hover for .cdt files
      if (!document.fileName.toLowerCase().endsWith('.cdt')) {
        return null;
      }
      
      console.log('Hover requested in CDT file at position:', position);
      const range = document.getWordRangeAtPosition(position, /\d+\.?\d*/);
      if (!range) {
        console.log('No range found');
        return null;
      }

      const word = document.getText(range);
      console.log('Word found:', word);
      const num = parseFloat(word);
      if (isNaN(num)) {
        console.log('Not a number');
        return null;
      }

      // Convert mm to imperial
      const imperial = mmToImperial(num);
      console.log('Converted to:', imperial);
      const contents = new vscode.MarkdownString(`**${num} mm** = ${imperial}`);
      return new vscode.Hover(contents, range);
    }
  });

  context.subscriptions.push(hoverProvider);
}

function mmToImperial(mm: number): string {
  const inches = mm / 25.4;
  const feet = Math.floor(inches / 12);
  const remainingInches = inches % 12;
  const sixteenths = Math.round(remainingInches * 16);

  let inchesWhole = Math.floor(sixteenths / 16);
  let sixteenthsRemainder = sixteenths % 16;

  if (sixteenthsRemainder === 0) {
    if (inchesWhole === 0) {
      return `${feet}'`;
    } else {
      return `${feet}'${inchesWhole}"`;
    }
  } else {
    const fractions: { [key: number]: string } = {
      2: '1/8',
      4: '1/4',
      6: '3/8',
      8: '1/2',
      10: '5/8',
      12: '3/4',
      14: '7/8'
    };
    const fraction = fractions[sixteenthsRemainder] || `${sixteenthsRemainder}/16`;
    if (inchesWhole === 0) {
      return `${feet}'${fraction}"`;
    } else {
      return `${feet}'${inchesWhole} ${fraction}"`;
    }
  }
}

export function deactivate() {}