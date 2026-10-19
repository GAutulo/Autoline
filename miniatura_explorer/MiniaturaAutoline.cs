// Prévia do projeto do Autoline (.autoline) no ícone do Explorer do Windows.
//
// É um "thumbnail handler" do Windows (IThumbnailProvider + IInitializeWithStream):
// o Explorer entrega o arquivo como um fluxo, este componente acha a miniatura
// que o Autoline grava logo no começo do arquivo (chave "miniatura", PNG em
// base64) e devolve a imagem. Arquivo sem miniatura (projeto antigo): devolve
// erro e o Explorer mostra o ícone normal.
//
// Compilado com o csc do .NET Framework 4 que já vem no Windows (ver
// compilar.bat). Registrado só pro usuário (HKCU) pelo Autoline — ver
// ui/associacao_arquivo.py. O Windows roda isto num processo separado
// (COM Surrogate), então um erro aqui não derruba o Explorer.

using System;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.IO;
using System.Runtime.InteropServices;
using System.Runtime.InteropServices.ComTypes;
using System.Text;

[assembly: System.Reflection.AssemblyVersion("1.0.0.0")]

namespace AutolineMiniatura
{
    [ComImport]
    [Guid("e357fccd-a995-4576-b01f-234630154e96")]
    [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    public interface IThumbnailProvider
    {
        void GetThumbnail(uint cx, out IntPtr phbmp, out uint pdwAlpha);
    }

    [ComImport]
    [Guid("b824b49d-22ac-4161-ac8a-9916e8fa3f7f")]
    [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    public interface IInitializeWithStream
    {
        void Initialize(IStream pstream, uint grfMode);
    }

    [ComVisible(true)]
    [Guid("7A3E2C51-9B4D-4F60-8C2E-5D1B0A6F4E21")]
    [ClassInterface(ClassInterfaceType.None)]
    public class MiniaturaAutoline : IThumbnailProvider, IInitializeWithStream
    {
        const int LimiteLeitura = 4 * 1024 * 1024; // a miniatura fica no começo; não lê logos inteiros
        const uint WTSAT_RGB = 1;
        byte[] _inicio;

        public void Initialize(IStream pstream, uint grfMode)
        {
            try
            {
                var memoria = new MemoryStream();
                var bloco = new byte[64 * 1024];
                IntPtr lidos = Marshal.AllocCoTaskMem(4);
                try
                {
                    while (memoria.Length < LimiteLeitura)
                    {
                        pstream.Read(bloco, bloco.Length, lidos);
                        int n = Marshal.ReadInt32(lidos);
                        if (n <= 0) break;
                        memoria.Write(bloco, 0, n);
                        if (TemMiniaturaCompleta(memoria)) break;
                    }
                }
                finally
                {
                    Marshal.FreeCoTaskMem(lidos);
                }
                _inicio = memoria.ToArray();
            }
            finally
            {
                Marshal.ReleaseComObject(pstream);
            }
        }

        static bool TemMiniaturaCompleta(MemoryStream memoria)
        {
            // Para de ler assim que a string da miniatura fechou.
            string texto = Encoding.ASCII.GetString(memoria.GetBuffer(), 0, (int)memoria.Length);
            int i = texto.IndexOf("\"miniatura\": \"", StringComparison.Ordinal);
            return i >= 0 && texto.IndexOf('"', i + 14) >= 0;
        }

        public void GetThumbnail(uint cx, out IntPtr phbmp, out uint pdwAlpha)
        {
            phbmp = IntPtr.Zero;
            pdwAlpha = WTSAT_RGB;
            byte[] png = ExtrairPng(_inicio);
            if (png == null)
                throw new COMException("Projeto sem miniatura", unchecked((int)0x80004005)); // E_FAIL: ícone normal
            using (var original = new Bitmap(new MemoryStream(png)))
            {
                int lado = (int)Math.Max(16, cx);
                double escala = Math.Min((double)lado / original.Width, (double)lado / original.Height);
                int largura = Math.Max(1, (int)Math.Round(original.Width * escala));
                int altura = Math.Max(1, (int)Math.Round(original.Height * escala));
                using (var final = new Bitmap(largura, altura, PixelFormat.Format24bppRgb))
                {
                    using (var g = Graphics.FromImage(final))
                    {
                        g.Clear(Color.White);
                        g.InterpolationMode = InterpolationMode.HighQualityBicubic;
                        g.SmoothingMode = SmoothingMode.HighQuality;
                        g.PixelOffsetMode = PixelOffsetMode.HighQuality;
                        g.DrawImage(original, 0, 0, largura, altura);
                    }
                    phbmp = final.GetHbitmap();
                }
            }
        }

        public static byte[] ExtrairPng(byte[] inicio)
        {
            if (inicio == null) return null;
            string texto = Encoding.ASCII.GetString(inicio);
            const string marca = "\"miniatura\": \"";
            int i = texto.IndexOf(marca, StringComparison.Ordinal);
            if (i < 0) return null;
            int comeco = i + marca.Length;
            int fim = texto.IndexOf('"', comeco);
            if (fim < 0) return null;
            try
            {
                return Convert.FromBase64String(texto.Substring(comeco, fim - comeco));
            }
            catch (FormatException)
            {
                return null;
            }
        }
    }
}
