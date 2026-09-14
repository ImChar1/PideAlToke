import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { InventarioService } from './services/inventario.service';
import { ItemInventario } from './models/inventario.model';

@Component({
  selector: 'app-inventario',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './inventario.component.html',
  styleUrl: './inventario.component.css'
})
export class InventarioComponent implements OnInit {
  private inventarioService = inject(InventarioService);

  inventario: ItemInventario[] = [];
  loading = true;
  error: string | null = null;

  ngOnInit(): void {
    this.inventarioService.getInventario().subscribe({
      next: (res: ItemInventario[]) => {
        this.inventario = res;
        this.loading = false;
      },
      error: (err) => {
        console.error('Error cargando inventario:', err);
        this.error = 'No se pudo conectar con ms-inventario.';
        this.loading = false;
      }
    });
  }
}